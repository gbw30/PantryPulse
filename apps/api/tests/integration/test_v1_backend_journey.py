# covers: V1-A07, V1-A10, V1-A14, V1-A15, V1-A16, V1-A23
"""W2-05: the v1 backend journey over HTTP on PostgreSQL, for a Pantry and a Retail network.

Import through the API (upload, commit, import.v1) → the follow-up enrichment.v1 (recorded Census
answers, the bundled ACS table) → a fixture forecast run (POST /networks/{id}/forecasts is 501
until W3) → frozen scenarios → or-comparison.v3 → saved results, decision actions and the CSV
export, with every stock table unchanged. One supervisor runs every job in-process with the
production registrations; only the Census transport is replayed and the fixture forecast job is
added. The session logs in under its own organization, never the network's. Never skipped in CI.
"""

import dataclasses
import hashlib
import json
import time
import uuid
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic import command
from fastapi.testclient import TestClient

import tests.integration.fake_driver as fake_driver
from app.main import create_app
from app.repositories.jobs import QueueRepository, TrustedScope, create_queue_engine
from app.schemas.v1_planning import METHODS_BY_MODE
from app.services.enrichment.census import CensusClient
from app.services.forecast_runtime import ForecastRuntime
from app.services.jobs.contracts import PRODUCTION_PROFILE, TERMINAL_STATES, AttemptState
from app.services.jobs.registry import Registry
from app.services.optimization.export import SIMULATED_NOTE
from app.services.optimization.v3 import PER_PRODUCT_LABEL
from app.workers.enrichment import ENRICHMENT_REGISTRATION, EnrichmentHandler
from app.workers.imports import REGISTRATION as IMPORT_REGISTRATION
from app.workers.optimization import V3_REGISTRATION
from app.workers.supervisor import Supervisor, SupervisorConfig
from tests.enrichment.test_enrichment_job import QUIET
from tests.enrichment.test_enrichment_postgres import Census
from tests.integration.wq_support import alembic_config, database_url, reset_schema
from tests.networks.test_build_scenario import FIXTURE_FORECAST, _forecast_output

pytestmark = pytest.mark.integration
SCHEMA = "w2_journey_test"
FIXTURES = Path(__file__).parents[1] / "networks" / "fixtures"
NAMES = ("locations", "products", "inventory", "demand_history", "inbound")
AS_OF = "2026-11-04"
TERMINAL = {s.value for s in TERMINAL_STATES}
# V1-A10: three pantries with neither coordinates nor rates, answered by the recorded geocoder:
# P4 matches exactly; P5 matches a different street (Non_Exact: stored but listed for review,
# W1-D06); P6 has no match, so its rates stay unknown and block EGP until the user excludes it.
UNLOCATED = ("P4,Pantry Four,pantry,73 W Flagler St,Miami,FL,33130,,,,,\n"
             "P5,Pantry Five,pantry,100 S Andrews Ave,Fort Lauderdale,FL,33301,,,,,\n"
             "P6,Pantry Six,pantry,99999 Nonexistent Pantry Rd,Tallahassee,FL,32301,,,,,\n")
MIAMI_TRACT = "12086003706"
# Everything the plan must never touch: the network's stock and every P1 stock table.
STOCK = (
    "net_batches", "net_inbound", "stock_ledger", "stock_commands", "inventory_lots",
    "receipts", "receipt_lines", "receipt_postings", "supply_receipts",
)


def fixture(name: str) -> tuple[dict[str, str], list[dict]]:
    folder = FIXTURES / name
    files = {n: (folder / f"{n}.csv").read_text() for n in NAMES}
    return files, json.loads((folder / "forecast.json").read_text())["series"]


@pytest.fixture
def stack(tmp_path, monkeypatch):
    url = database_url()
    reset_schema(url, SCHEMA)
    engine = create_queue_engine(url, schema=SCHEMA)
    presenter = uuid.uuid4()  # the session's own organization; every network gets its own
    with engine.begin() as conn:
        command.upgrade(alembic_config(conn), "head")
        conn.execute(sa.text(
            "INSERT INTO organizations (id, name, is_demo) VALUES (:o, 'presenter', false)"),
            {"o": presenter})
    monkeypatch.setenv("PP_IMPORT_DIR", str(tmp_path))
    monkeypatch.setattr(fake_driver, "_behavior_for", lambda validated, step: QUIET)
    monkeypatch.setattr(fake_driver, "_with_behavior", lambda validated, step, b: validated)
    census = Census()
    registry = Registry([
        IMPORT_REGISTRATION,
        dataclasses.replace(ENRICHMENT_REGISTRATION,
                            handler=EnrichmentHandler(CensusClient(census))),
        V3_REGISTRATION,
        FIXTURE_FORECAST,
    ])
    queue = QueueRepository(engine, registry=registry, profile=PRODUCTION_PROFILE)
    supervisor = Supervisor(queue, registry, fake_driver.FakeDriver(registry=registry),
                            SupervisorConfig(registry_name="test", profile=PRODUCTION_PROFILE,
                                             tick_s=0.02))
    assert supervisor.start()
    salt = "37" * 16
    digest = hashlib.scrypt(b"test-password", salt=bytes.fromhex(salt), n=16384, r=8, p=1,
                            dklen=64).hex()
    for k, v in dict(
        PP_PRESENTER_USERNAME="tester",
        PP_PRESENTER_PASSWORD_HASH=f"scrypt$16384$8$1${salt}${digest}",
        PP_PRESENTER_ORGANIZATION_ID=str(presenter),
        PP_COOKIE_SECURE="false",
        PP_ALLOWED_ORIGINS="http://testserver",
    ).items():
        monkeypatch.setenv(k, v)
    try:
        with TestClient(create_app(ForecastRuntime(engine, queue))) as client:
            login = client.post("/api/v1/presenter/login",
                                json=dict(username="tester", password="test-password"),
                                headers={"Origin": "http://testserver"})
            assert login.status_code == 200, login.text
            headers = {"Origin": "http://testserver", "X-CSRF-Token": login.json()["csrf_token"]}
            yield SimpleNamespace(client=client, headers=headers, engine=engine, queue=queue,
                                  supervisor=supervisor, census=census)
    finally:
        supervisor.shutdown_drain(timeout_s=5)
        engine.dispose()
        reset_schema(url, SCHEMA)


def settle(stack, status_url: str, timeout_s: float = 120) -> dict:
    """Tick the supervisor until the job, read through GET /jobs/{id}, is terminal."""
    end = time.monotonic() + timeout_s
    while time.monotonic() < end:
        stack.supervisor.tick()
        job = stack.client.get(status_url)
        assert job.status_code == 200, job.text  # under the network's organization
        if job.json()["state"] in TERMINAL:
            return job.json()
        time.sleep(0.01)
    raise AssertionError(f"{status_url} did not settle")


def import_network(stack, files: dict[str, str], mode: str) -> dict:
    client, headers = stack.client, stack.headers
    created = client.post("/api/v1/imports", headers=headers, json={"network": {
        "name": f"Journey {mode.title()}", "mode": mode, "timezone": "America/New_York"}})
    assert created.status_code == 201, created.text
    assert created.json()["network_id"] is None  # no network row until the commit succeeds
    import_id = created.json()["import_id"]
    for name, text in files.items():
        stored = client.post(f"/api/v1/imports/{import_id}/files/{name}", content=text.encode(),
                             headers=headers | {"Content-Type": "text/csv"})
        assert stored.status_code == 200, stored.text
    accepted = client.post(f"/api/v1/imports/{import_id}/commit", json={"as_of_date": AS_OF},
                           headers=headers | {"Idempotency-Key": f"commit-{import_id}"})
    assert accepted.status_code == 202, accepted.text
    assert accepted.json()["status_url"] == f"/api/v1/imports/{import_id}"
    end = time.monotonic() + 120
    while (status := client.get(f"/api/v1/imports/{import_id}").json())["phase"] not in (
            "done", "failed"):
        assert time.monotonic() < end, "import.v1 did not settle"
        stack.supervisor.tick()
        time.sleep(0.01)
    assert status["phase"] == "done", status
    return status


def enrichment(stack, network_id: str, timeout_s: float = 60) -> dict:
    """Run the import's follow-up enrichment.v1 to its end (max_queued is 2, so drain it)."""
    end = time.monotonic() + timeout_s
    while (body := stack.client.get(f"/api/v1/networks/{network_id}/enrichment").json())[
            "state"] == "running":
        assert time.monotonic() < end, "enrichment.v1 did not settle"
        stack.supervisor.tick()
        time.sleep(0.01)
    return body


def forecast_run(stack, status: dict, series: list[dict]) -> str:
    """The fixture forecast run W1 used: its publisher inserts the forecast_runs row."""
    network = SimpleNamespace(network_id=uuid.UUID(status["network_id"]),
                              dataset_version_id=uuid.UUID(status["dataset_version_id"]))
    cutoff = date.fromisoformat(status["as_of_date"])
    org, output = _forecast_output(stack.engine, network, cutoff, series)
    scope = TrustedScope(org, "test")
    accepted = stack.queue.submit(scope, FIXTURE_FORECAST.contract, {
        "dataset_id": status["dataset_version_id"], "planning_ready": True, "output": output},
        str(uuid.uuid4()))
    end = time.monotonic() + 30
    while (job := stack.queue.get_job(scope, accepted.job_id)).state not in TERMINAL_STATES:
        assert time.monotonic() < end, "fixture forecast run did not settle"
        stack.supervisor.tick()
        time.sleep(0.01)
    assert job.state == AttemptState.SUCCEEDED, job
    return job.attempts[-1].result_manifest["forecast_run_id"]


def snapshot(engine) -> dict[str, str]:
    """A digest of every row of every stock table, so a changed quantity shows, not just a count."""
    with engine.connect() as conn:
        return {t: conn.scalar(sa.text(
            f"SELECT md5(coalesce(string_agg(r::text, '|' ORDER BY r::text), '')) FROM {t} r"))
            for t in STOCK}


def scenario(stack, status: dict, run_id: str, transfer_mode: str, **options) -> dict:
    created = stack.client.post(
        f"/api/v1/networks/{status['network_id']}/scenarios", headers=stack.headers,
        json={"dataset_version_id": status["dataset_version_id"], "forecast_run_id": run_id,
              "transfer_mode": transfer_mode, **options})
    assert created.status_code == 201, created.text
    return created.json()


def compare(stack, network_id: str, frozen: dict, measure: str) -> dict:
    """Submit every method of the mode, run the job, and return the saved comparison."""
    mode = frozen["payload"]["mode"]
    accepted = stack.client.post(
        f"/api/v1/networks/{network_id}/comparisons",
        json={"scenario_id": frozen["id"], "methods": list(METHODS_BY_MODE[mode]),
              "measure": measure},
        headers=stack.headers | {"Idempotency-Key": f"{frozen['id']}-{measure}"})
    assert accepted.status_code == 202, accepted.text
    assert settle(stack, accepted.json()["status_url"])["state"] == "SUCCEEDED"
    saved = stack.client.get(accepted.json()["result_url"])
    assert saved.status_code == 200, saved.text
    body = saved.json()
    result = body["result"]
    assert (result["scenario_id"], result["scenario_hash"]) == (
        frozen["id"], frozen["content_hash"])
    assert [m["method"] for m in result["methods"]] == list(METHODS_BY_MODE[mode])
    for m in result["methods"]:
        assert (m["verified"], m["failure_reason"], m["measure"]) == (True, None, measure), m
        if m["native_status"] is not None:  # an optimizer: labeled, products named
            assert PER_PRODUCT_LABEL in m["labels"], m["labels"]
            assert m["products"], m
    return body


def decide_and_export(stack, saved: dict, method: str) -> None:
    """Every transfer is an action with action/why/effect; the export changes no stock."""
    [chosen] = [m for m in saved["result"]["methods"] if m["method"] == method]
    assert chosen["transfers"], f"{method} moved nothing; the fixture should make it move stock"
    base = f"/api/v1/networks/{saved['network_id']}/comparisons/{saved['id']}/methods/{method}"
    actions = stack.client.get(f"{base}/actions")
    assert actions.status_code == 200, actions.text
    body = actions.json()
    assert {a["id"] for a in body["actions"]} == {t["id"] for t in chosen["transfers"]}
    assert all(a["action_text"].strip() and a["why_text"].strip() for a in body["actions"])
    assert body["non_additive_label"].startswith("effect of this action given the rest")
    ids = [a["id"] for a in body["actions"]]
    exported = stack.client.post(f"{base}/export", json={"action_ids": ids}, headers=stack.headers)
    assert exported.status_code == 200, exported.text
    assert exported.headers["content-type"].startswith("text/csv")
    lines = exported.text.strip().splitlines()
    assert len(lines) == 1 + len(ids)
    assert all(saved["result"]["scenario_hash"] in line and SIMULATED_NOTE in line
               for line in lines[1:])


def test_import_to_export_pantry(stack):
    files, series = fixture("mini-network")
    files["locations"] += UNLOCATED
    status = import_network(stack, files, "PANTRY")
    network_id = status["network_id"]
    assert [(r["location_id"], r["arrival_date"]) for r in status["outside_horizon_inbound"]] == [
        ("P1", "2026-11-20")]

    enriched = enrichment(stack, network_id)
    assert (enriched["state"], enriched["last_error"]) == ("done", None)
    # Only the locations without coordinates were sent to the geocoder.
    assert sorted(sum(stack.census.calls, [])) == [
        "100 S Andrews Ave", "73 W Flagler St", "99999 Nonexistent Pantry Rd"]
    attributes = {loc["location_id"]: loc for loc in enriched["locations"]}
    assert attributes["P4"]["state"] == "known", attributes["P4"]
    assert attributes["P4"]["source"] == f"ACS 5-year 2024, tract {MIAMI_TRACT}"
    assert None not in (attributes["P4"]["poverty_rate"], attributes["P4"]["snap_rate"])
    unmatched = {u["location_id"]: u["hint"] for u in enriched["unmatched"]}
    assert sorted(unmatched) == ["P5", "P6"]
    assert "100 N ANDREWS AVE" in unmatched["P5"]  # the address Census matched, for review
    assert "latitude and longitude" in unmatched["P6"]
    assert [(b["location_id"], b["missing"]) for b in enriched["egp_blockers"]] == [
        ("P6", ["poverty_rate", "snap_rate"])]
    located = stack.client.get(f"/api/v1/networks/{network_id}/locations").json()["locations"]
    sources = {loc["location_id"]: loc["coordinates_source"] for loc in located}
    assert sources == {"H1": "user", "P1": "user", "P2": "user", "P3": "user",
                       "P4": "census_geocoder", "P5": "census_geocoder", "P6": None}

    run_id = forecast_run(stack, status, series)
    blocked = stack.client.post(
        f"/api/v1/networks/{network_id}/scenarios", headers=stack.headers,
        json={"dataset_version_id": status["dataset_version_id"], "forecast_run_id": run_id,
              "transfer_mode": "HUB_ONLY", "planning_days": 2})
    assert blocked.status_code == 422, blocked.text
    assert blocked.json()["error"]["code"] == "EGP_ATTRIBUTES_UNRESOLVED"
    assert [b["location_id"] for b in blocked.json()["error"]["details"]["locations"]] == ["P6"]
    excluded = stack.client.put(f"/api/v1/networks/{network_id}/locations/P6/attributes",
                                json={"excluded": True}, headers=stack.headers)
    assert excluded.status_code == 200 and excluded.json()["state"] == "excluded", excluded.text

    before = snapshot(stack.engine)
    for transfer_mode in ("HUB_ONLY", "HUB_AND_PANTRY"):
        frozen = scenario(stack, status, run_id, transfer_mode, planning_days=2)
        payload = frozen["payload"]
        assert (payload["transfer_mode"], payload["planning_days"]) == (transfer_mode, 2)
        assert payload["inbound_file_provided"] is True
        assert [(i["location_id"], i["arrival_date"]) for i in payload["inbound"]] == [
            ("P2", "2026-11-06")]  # in the horizon, counted once; P1's 11-20 row is listed
        assert sorted(v["location_id"] for v in payload["vulnerability"]) == [
            "P1", "P2", "P3", "P4", "P5"]  # P6 excluded by the user, and listed as such
        assert any("P6 excluded from EGP by the user" in a for a in payload["assumptions"])
        saved = compare(stack, network_id, frozen, "UNITS")
        decide_and_export(stack, saved, "EGP_PI_INSPIRED")
    assert snapshot(stack.engine) == before


def test_import_to_export_retail(stack):
    files, series = fixture("retail-twin")
    status = import_network(stack, files, "RETAIL")
    network_id = status["network_id"]
    assert [(r["location_id"], r["arrival_date"]) for r in status["outside_horizon_inbound"]] == [
        ("S2", "2026-11-25")]
    enriched = enrichment(stack, network_id)
    assert (enriched["state"], enriched["last_error"], enriched["unmatched"]) == (
        "done", None, [])
    assert stack.census.calls == []  # every location came with coordinates

    run_id = forecast_run(stack, status, series)
    before = snapshot(stack.engine)
    frozen = scenario(stack, status, run_id, "HUB_ONLY")
    payload = frozen["payload"]
    assert (payload["mode"], payload["planning_days"], payload["policy"]) == ("RETAIL", None, None)
    assert [(i["location_id"], i["arrival_date"]) for i in payload["inbound"]] == [
        ("S3", "2026-11-07")]
    for measure in ("UNITS", "USD"):
        saved = compare(stack, network_id, frozen, measure)
        assert all(m["usd_unavailable_reason"] is None for m in saved["result"]["methods"])
        decide_and_export(stack, saved, "RETAIL_OPTIMIZED")
    assert snapshot(stack.engine) == before
