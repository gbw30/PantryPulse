"""Real HTTP + PostgreSQL + native solve; no claim of Linux worker containment."""

from datetime import timedelta
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from test_forecast_api_postgres import advertise, compute
from test_forecast_api_postgres import api as api
from test_forecast_api_postgres import forecast_storage as forecast_storage

from app.models import operational as m
from app.services.jobs.contracts import StepOutcome, StepStatus
from app.services.jobs.registry import ExecutionContext
from app.workers.registries import load_registry
from scripts.allocation_fixture import fixture

pytestmark = pytest.mark.integration


def post(client, headers, url, body, key=None):
    return client.post(url, json=body, headers=headers | {"Idempotency-Key": key or uuid4().hex})


def test_saved_scenarios_modes_native_publication_comparison_and_review(api):
    client, headers, runtime, demo = api
    package, policy, original = fixture(UUID(demo["organization_id"]))
    response = post(client, headers, "/api/v1/or/input-packages", package.model_dump(mode="json"))
    assert response.status_code == 201, response.text
    package_id = response.json()["result"]["id"]
    response = post(client, headers, "/api/v1/or/policies", policy.model_dump(mode="json"))
    assert response.status_code == 201, response.text
    policy_id = response.json()["result"]["id"]
    request = dict(
        input_package_id=package_id,
        policy_id=policy_id,
        planning_days=2,
        modifiers=[row.model_dump(mode="json") for row in original.modifiers],
        intent="CURRENT",
        expected_source_revision=package.source_revision_token,
    )
    assert post(client, headers, "/api/v1/scenarios", request).status_code == 422
    saved = {}
    for mode in ("HUB_ONLY", "HUB_AND_PANTRY"):
        response = post(client, headers, "/api/v1/scenarios", request | {"transfer_mode": mode})
        assert response.status_code == 201, response.text
        data = response.json()["result"]
        saved[mode] = data
        row = client.get(f"/api/v1/scenarios/{data['id']}")
        assert row.status_code == 200 and row.json()["transfer_mode"] == mode
    for data in saved.values():
        rejected = post(
            client,
            headers,
            f"/api/v1/scenarios/{data['id']}/plans",
            dict(
                expected_scenario_hash=data["operational_hash"],
                intent="CURRENT",
                method="CLASSICAL_GP",
            ),
        )
        assert rejected.status_code == 503, rejected.text
    own = advertise(runtime.queue, contracts=list(load_registry("production").contracts()))
    try:
        data = saved["HUB_AND_PANTRY"]
        response = post(
            client,
            headers,
            f"/api/v1/scenarios/{data['id']}/compare-methods",
            dict(expected_scenario_hash=data["operational_hash"], intent="CURRENT"),
        )
        assert response.status_code == 202, response.text
        accepted = response.json()
        claim = runtime.queue.claim_next(own)
        assert claim is not None and claim.contract == "or-comparison-v1"
        reg = load_registry("production").get(claim.contract)
        frozen = claim.input_package["input"]
        outcomes = []
        for method in ("CLASSICAL_GP", "EGP_PI_INSPIRED"):
            context = ExecutionContext(claim.job_id, claim.attempt_id, method, 50, 15)
            output = reg.handler.execute_step(method, frozen, (), context)
            assert output["outcome"] == "VERIFIED"
            outcomes.append(StepOutcome(method, StepStatus.COMPLETED, output=output))
        runtime.queue.publish(own, claim, reg.publisher.validate(frozen, outcomes))
        assert client.get(accepted["status_url"]).json()["state"] == "SUCCEEDED"
        results = client.get(accepted["result_url"])
        assert results.status_code == 200, results.text
        assert len(results.json()["plans"]) == 2
        assert len(results.json()["comparisons"]) == 1
        plan = results.json()["plans"][0]
        key = uuid4().hex
        review_body = dict(
            action="REVIEWED",
            expected_result_hash=plan["result_hash"],
            note="Simulation reviewed; no stock movement",
        )
        reviewed = post(client, headers, f"/api/v1/plans/{plan['id']}/review", review_body, key)
        assert reviewed.status_code == 201, reviewed.text
        assert (
            post(client, headers, f"/api/v1/plans/{plan['id']}/review", review_body, key).json()
            == reviewed.json()
        )
        with runtime.engine.connect() as conn:
            assert conn.scalar(sa.select(sa.func.count()).select_from(m.InventoryLot)) == 0
            assert conn.scalar(sa.select(sa.func.count()).select_from(m.StockLedgerEntry)) == 0
    finally:
        runtime.queue.release(own)


def test_real_source_capture_forecast_dashboard_and_shortages(api):
    client, headers, runtime, demo = api
    # Build an actual saved baseline from existing history with a current cutoff.
    own = advertise(runtime.queue)
    try:
        with runtime.engine.connect() as conn:
            now = conn.scalar(sa.select(sa.func.clock_timestamp()))
        from zoneinfo import ZoneInfo

        cutoff = now.astimezone(ZoneInfo("America/New_York")).date() - timedelta(days=1)
        request = demo["request"] | dict(
            data_cutoff_date=cutoff.isoformat(),
            snapshot_as_of=now.isoformat(),
            policy=demo["request"]["policy"] | {"strategy": "MOVING_AVERAGE"},
        )
        accepted = post(client, headers, "/api/v1/forecasts", request)
        assert accepted.status_code == 202, accepted.text
        claim, output = compute(runtime.queue, own)
        runtime.queue.publish(own, claim, output)
        result = client.get(accepted.json()["result_url"]).json()
        run_id = result["forecast"]["run_id"]
    finally:
        runtime.queue.release(own)
    summary = client.get("/api/v1/dashboard/summary")
    assert summary.status_code == 200, summary.text
    assert len(summary.json()["inventory"]) == 14
    shortages = client.get(f"/api/v1/shortages/{run_id}")
    assert shortages.status_code == 200, shortages.text
    assert len(shortages.json()["series"]) == 12
    assert all(
        point["served"] == "0" for row in shortages.json()["series"] for point in row["days"]
    )
    catalog = client.get("/api/v1/operational-catalog").json()
    sites, products = catalog["sites"], catalog["products"]
    _, policy, _ = fixture()
    capacity = dict(original=1000, fixed_used=0, residual=1000, source_revision="simulated-v1")
    configuration = dict(
        forecast_run_id=run_id,
        expected_source_revision=None,
        products=[
            dict(
                id=row["id"],
                unit=row["base_unit"],
                handling_coefficient=1,
                source_revision="simulated-v1",
            )
            for row in products
        ],
        routes=[],
        capacities=dict(
            sites=[
                dict(
                    site_id=row["id"],
                    source=capacity,
                    receiving=[capacity] * 7,
                    storage=[capacity] * 7,
                )
                for row in sites
            ],
            global_handling=capacity,
            cost_budget_minor=None,
        ),
        reserves=[
            dict(site_id=site["id"], product_id=product["id"], floors=[0] * 7)
            for site in sites
            for product in products
        ],
        vulnerability_attributes=[
            dict(
                site_id=site["id"],
                scores=[
                    dict(
                        attribute_id=coefficient.attribute_id,
                        score_bp=5000,
                        raw_note="Synthetic test",
                        transformation="identity",
                        transformation_version="test-v1",
                        classification="SIMULATED",
                    )
                    for coefficient in policy.coefficients
                ],
            )
            for site in sites
            if site["role"] == "BENEFICIARY"
        ],
    )
    captured = post(client, headers, "/api/v1/or/input-packages/from-sources", configuration)
    assert captured.status_code == 201, captured.text
    record = client.get(f"/api/v1/or/input-packages/{captured.json()['result']['id']}")
    assert record.status_code == 200
    package = record.json()["payload"]
    assert len(package["forecasts"]) == 14
    assert package["inventory"] == []
    # Existing history mutation invalidates current source identity, not saved reads.
    with runtime.engine.begin() as conn:
        conn.execute(
            sa.update(m.Product)
            .where(m.Product.id == UUID(products[0]["id"]))
            .values(name="Updated product label")
        )
    policy_id = post(client, headers, "/api/v1/or/policies", policy.model_dump(mode="json")).json()[
        "result"
    ]["id"]
    modifiers = [
        dict(
            site_id=site["id"],
            product_id=product["id"],
            mode="CENTRAL",
            multiplier="1",
            buffer_fraction=None,
        )
        for site in sites
        for product in products
    ]
    scenario = post(
        client,
        headers,
        "/api/v1/scenarios",
        dict(
            input_package_id=record.json()["id"],
            policy_id=policy_id,
            transfer_mode="HUB_ONLY",
            planning_days=2,
            modifiers=modifiers,
            intent="CURRENT",
            expected_source_revision=package["source_revision_token"],
        ),
    )
    assert scenario.status_code == 409, scenario.text
