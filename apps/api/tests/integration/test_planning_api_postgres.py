"""Canonical planning extension: real persisted source snapshot, native solves and reviews."""

from uuid import uuid4

import pytest
import sqlalchemy as sa
from test_planning_postgres import api as api
from test_planning_postgres import complete
from test_planning_postgres import planning_storage as planning_storage
from test_planning_postgres import saved_plan as saved_plan

from app.models import operational as m
from app.models.optimization import PlanningPlan, PlanningReview
from app.services.jobs.contracts import PRODUCTION_PROFILE, SupervisorState
from app.services.jobs.policies import supervisor_advertisement
from app.workers.registries import load_registry

pytestmark = pytest.mark.integration


def post(client, headers, path, body, key=None):
    return client.post(path, json=body, headers=headers | {"Idempotency-Key": key or uuid4().hex})


def test_canonical_single_plans_pair_review_and_tenant_isolation(saved_plan, monkeypatch):
    client, headers, rt, demo = saved_plan
    scenario = client.get("/api/v1/planning-catalog").json()["scenarios"][0]
    snapshot = client.get(f"/api/v1/scenarios/{scenario['id']}").json()
    body = dict(expected_scenario_hash=snapshot["payload"]["operational_hash"], search_seconds=1)
    path = f"/api/v1/scenarios/{scenario['id']}/plans"
    assert (
        post(
            client,
            headers,
            path,
            body | {"method": "CLASSICAL_GP", "expected_scenario_hash": "0" * 64},
        ).status_code
        == 409
    )
    assert post(client, headers, path, body | {"method": "CLASSICAL_GP"}).status_code == 503
    q = rt.queue
    own = q.acquire_ownership(
        supervisor_id=uuid4(),
        host_identity="DIRECT_NATIVE_TEST",
        effective_limits=supervisor_advertisement(
            PRODUCTION_PROFILE,
            handler_contracts=load_registry("production").contracts(),
            process_containment=True,
        ),
    )
    assert own and q.set_state(own, SupervisorState.READY)
    with rt.engine.connect() as conn:
        before = conn.scalar(sa.select(sa.func.count()).select_from(m.StockLedgerEntry))
    saved_ids = []
    try:
        for method in ("CLASSICAL_GP", "EGP_PI_INSPIRED"):
            q.heartbeat(own)
            accepted = post(client, headers, path, body | {"method": method})
            assert accepted.status_code == 202, accepted.text
            claim = complete(q, own)
            assert claim.contract == "or-allocation.v2" and claim.budget_s == 31
            result = client.get(accepted.json()["result_url"])
            assert result.status_code == 200, result.text
            plan = result.json()["plans"][0]
            saved_ids.append(plan["id"])
            assert (
                plan["result"]["outcome"] == "VERIFIED" and plan["result"]["verification"]["passed"]
            )
            assert plan["settings"]["search_milliseconds"] == 1000
            assert client.get(f"/api/v1/plans/{plan['id']}").status_code == 200
            review = dict(
                action="REVIEWED", expected_result_hash=plan["result_hash"], note="Simulation only"
            )
            review_path = f"/api/v1/plans/{plan['id']}/review"
            key = uuid4().hex
            response = post(client, headers, review_path, review, key)
            assert response.status_code == 201, response.text
            assert post(client, headers, review_path, review, key).json() == response.json()
            assert (
                post(client, headers, review_path, review | {"action": "REJECTED"}, key).status_code
                == 409
            )
            assert (
                post(
                    client, headers, review_path, review | {"expected_result_hash": "0" * 64}
                ).status_code
                == 409
            )
        q.heartbeat(own)
        accepted = post(
            client, headers, f"/api/v1/scenarios/{scenario['id']}/compare-methods", body
        )
        assert accepted.status_code == 202, accepted.text
        # Exact frozen inputs/settings can reuse the prior canonical comparison.
        if not accepted.json()["replayed"]:
            complete(q, own)
        pair = client.get(f"/api/v1/allocation-jobs/{accepted.json()['job_id']}/results")
        assert pair.status_code == 200 and len(pair.json()["plans"]) == 2, pair.text
        assert pair.json()["comparison_id"] == accepted.json()["job_id"]
        with rt.engine.connect() as conn:
            assert conn.scalar(sa.select(sa.func.count()).select_from(m.StockLedgerEntry)) == before
        for model in (PlanningPlan, PlanningReview):
            with pytest.raises(sa.exc.IntegrityError), rt.engine.begin() as conn:
                conn.execute(sa.delete(model))
        with rt.engine.begin() as conn:
            other = uuid4()
            conn.execute(
                sa.insert(m.Organization).values(id=other, name="Other tenant", is_demo=True)
            )
        monkeypatch.setenv("PP_PRESENTER_ORGANIZATION_ID", str(other))
        login = client.post(
            "/api/v1/presenter/login",
            json=dict(username="tester", password="test-password"),
            headers={"Origin": "http://testserver"},
        )
        assert login.status_code == 200
        for identity in saved_ids:
            assert client.get(f"/api/v1/plans/{identity}").status_code == 404
        assert client.get(accepted.json()["status_url"]).status_code == 404
    finally:
        q.release(own)


def test_real_linux_single_plan_cancel_retry_and_fenced_publication(saved_plan):
    import time
    from pathlib import Path

    from app.workers.process_driver import PosixProcessDriver, linux_containment_available
    from app.workers.supervisor import Supervisor, SupervisorConfig

    if not linux_containment_available():
        pytest.skip("Requires Linux containment")
    client, headers, rt, _ = saved_plan
    scenario = client.get("/api/v1/planning-catalog").json()["scenarios"][0]
    snapshot = client.get(f"/api/v1/scenarios/{scenario['id']}").json()
    driver = PosixProcessDriver(cwd=str(Path(__file__).resolve().parents[2]))
    supervisor = Supervisor(
        rt.queue, rt.queue.registry, driver, SupervisorConfig("production", PRODUCTION_PROFILE)
    )
    assert supervisor.start()
    try:
        response = post(
            client,
            headers,
            f"/api/v1/scenarios/{scenario['id']}/plans",
            dict(
                expected_scenario_hash=snapshot["payload"]["operational_hash"],
                method="CLASSICAL_GP",
                search_seconds=2,
            ),
        )
        assert response.status_code == 202, response.text
        accepted = response.json()
        supervisor.tick()  # Actual Linux child started inside the recorded boundary.
        assert client.get(accepted["status_url"]).json()["state"] == "RUNNING"
        cancelled = post(client, headers, f"/api/v1/jobs/{accepted['job_id']}/cancel", {})
        assert cancelled.status_code == 202, cancelled.text
        end = time.monotonic() + 30
        while time.monotonic() < end:
            supervisor.tick()
            if client.get(accepted["status_url"]).json()["state"] == "CANCELLED":
                break
            time.sleep(0.05)
        assert client.get(accepted["status_url"]).json()["state"] == "CANCELLED"
        assert client.get(accepted["result_url"]).json()["plans"] == []
        retry = post(client, headers, f"/api/v1/jobs/{accepted['job_id']}/retry", {})
        assert retry.status_code == 202 and retry.json()["result_url"] == accepted["result_url"]
        end = time.monotonic() + 30
        while time.monotonic() < end:
            supervisor.tick()
            state = client.get(accepted["status_url"]).json()["state"]
            if state in {"SUCCEEDED", "FAILED", "TIMED_OUT"}:
                break
            time.sleep(0.05)
        assert state == "SUCCEEDED"
        result = client.get(accepted["result_url"]).json()["plans"][0]
        assert result["settings"]["search_milliseconds"] == 2000
        assert result["result"]["verification"]["passed"] is True
        supervisor.shutdown_drain()
    finally:
        supervisor.close()


def test_shortage_rejects_same_timezone_calendar_version_change(saved_plan):
    client, _, rt, _ = saved_plan
    scenario = client.get("/api/v1/planning-catalog").json()["scenarios"][0]
    snapshot = client.get(f"/api/v1/scenarios/{scenario['id']}").json()
    forecast_id = snapshot["forecast_run_id"]
    assert client.get(f"/api/v1/shortages/{forecast_id}").status_code == 200
    with rt.engine.begin() as conn:
        site = (
            conn.execute(sa.select(m.Site.__table__).where(m.Site.role == "BENEFICIARY"))
            .mappings()
            .first()
        )
        calendar = (
            conn.execute(
                sa.select(m.SiteCalendar.__table__).where(
                    m.SiteCalendar.id == site["current_calendar_id"]
                )
            )
            .mappings()
            .one()
        )
        changed = uuid4()
        conn.execute(
            sa.insert(m.SiteCalendar).values(
                id=changed,
                organization_id=site["organization_id"],
                site_id=site["id"],
                revision=calendar["revision"] + 1,
                timezone=calendar["timezone"],
            )
        )
        conn.execute(
            sa.update(m.Site).where(m.Site.id == site["id"]).values(current_calendar_id=changed)
        )
    response = client.get(f"/api/v1/shortages/{forecast_id}")
    assert (
        response.status_code == 409
        and response.json()["error"]["code"] == "FORECAST_UNIT_OR_CALENDAR_CHANGED"
    )
