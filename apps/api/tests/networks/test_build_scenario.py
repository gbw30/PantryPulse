# covers: V1-A10, V1-A23
"""Network → frozen or-input-v3 scenario on PostgreSQL (W1-D09).

The mini network (fixtures/mini-network: 1 hub, 3 pantries, 2 products) is imported through
the real import path. Its forecast run comes from a fixture job: a real supervisor runs
`fixture.forecast-run.v1`, whose publisher inserts the forecast_runs row inside the
publication transaction, as W3's forecast.v1 will (the forecast lane starts in W3)."""

import dataclasses
import json
import time
import uuid
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic import command

import tests.integration.fake_driver as fake_driver
from app.repositories.jobs import QueueRepository, TrustedScope, create_queue_engine
from app.schemas.v1_enrichment import LocationAttributesUpdate
from app.schemas.v1_imports import NewNetwork
from app.schemas.v1_planning import ORInputV3, ReserveV3, ScenarioOptions
from app.services.enrichment.api import set_location_attributes
from app.services.forecasting.schemas import (
    Diagnostics,
    ForecastOutput,
    ForecastPoint,
    ForecastSeriesResult,
    ProviderIdentity,
    SeriesKey,
    SeriesScope,
    StructuredError,
)
from app.services.jobs.contracts import TERMINAL_STATES, AttemptState, OperationKind, StepSpec
from app.services.jobs.registry import InputRejected, Registration, Registry
from app.services.networks.api import create_scenario
from app.services.optimization.canonical import operational_hash
from app.services.presenter_access import AccessError
from app.workers.supervisor import Supervisor, SupervisorConfig
from tests.enrichment.test_enrichment_job import PROFILE, QUIET
from tests.imports.test_import_postgres import _import
from tests.integration.wq_support import alembic_config, database_url, reset_schema

pytestmark = pytest.mark.integration
SCHEMA = "w1_data_scenario_test"
SCOPE = TrustedScope(uuid.UUID(int=1), "local")
FIXTURE = Path(__file__).parent / "fixtures" / "mini-network"
FILES = {name: (FIXTURE / f"{name}.csv").read_text()
         for name in ("locations", "products", "inventory", "demand_history", "inbound")}
FORECAST = json.loads((FIXTURE / "forecast.json").read_text())
AS_OF = date(2026, 11, 4)
NO_LIMIT = "capacity not provided — no limit assumed"


# --- the fixture forecast run --------------------------------------------------------------

class FixtureForecastHandler:
    def validate_input(self, payload):
        return dict(payload)

    def steps(self, validated, profile):
        return (StepSpec(name="fixture", min_s=profile.method_min_s),)

    def execute_step(self, step, validated, prior, context):
        return {}


class FixtureForecastPublisher:
    def validate(self, validated, outcomes):
        return dict(validated)

    def publish(self, connection, identity, package):
        run_id = uuid.uuid4()
        connection.execute(sa.text(
            "INSERT INTO forecast_runs (id, organization_id, job_id, attempt_id, input_hash, "
            "planning_ready, frozen_input, output) VALUES (:id, :org, :job, :attempt, :hash, "
            ":ready, CAST(:frozen AS jsonb), CAST(:output AS jsonb))"),
            {"id": run_id, "org": identity.organization_id, "job": identity.job_id,
             "attempt": identity.attempt_id, "hash": package["output"]["input_hash"],
             "ready": package["planning_ready"],
             "frozen": json.dumps({"dataset_id": package["dataset_id"]}),
             "output": json.dumps({**package["output"], "run_id": str(run_id)})})
        return {"forecast_run_id": str(run_id)}


FIXTURE_FORECAST = Registration(
    contract="fixture.forecast-run.v1", operation_kind=OperationKind.FORECAST,
    input_schema_version="1", max_input_bytes=1_000_000, max_output_bytes=10_000,
    handler=FixtureForecastHandler(), publisher=FixtureForecastPublisher())


@pytest.fixture(scope="module")
def engine():
    url = database_url()
    reset_schema(url, SCHEMA)
    eng = create_queue_engine(url, schema=SCHEMA)
    with eng.begin() as conn:
        command.upgrade(alembic_config(conn), "head")
    yield eng
    eng.dispose()
    reset_schema(url, SCHEMA)


@pytest.fixture
def forecasts(engine, monkeypatch):
    monkeypatch.setattr(fake_driver, "_behavior_for", lambda validated, step: QUIET)
    monkeypatch.setattr(fake_driver, "_with_behavior", lambda validated, step, b: validated)
    registry = Registry([FIXTURE_FORECAST])
    queue = QueueRepository(engine, registry=registry, profile=PROFILE)
    supervisor = Supervisor(queue, registry, fake_driver.FakeDriver(registry=registry),
                            SupervisorConfig(registry_name="test", profile=PROFILE, tick_s=0.02))
    assert supervisor.start()

    def make(network, *, dataset_id=None, ready=True, cutoff=AS_OF, series=FORECAST["series"]):
        org, output = _forecast_output(engine, network, cutoff, series)
        accepted = queue.submit(TrustedScope(org, "test"), FIXTURE_FORECAST.contract, {
            "dataset_id": str(dataset_id or network.dataset_version_id), "planning_ready": ready,
            "output": output}, str(uuid.uuid4()))
        end = time.monotonic() + 10
        while time.monotonic() < end:
            supervisor.tick()
            job = queue.get_job(TrustedScope(org, "test"), accepted.job_id)
            if job.state in TERMINAL_STATES:
                assert job.state == AttemptState.SUCCEEDED, job
                return uuid.UUID(job.attempts[-1].result_manifest["forecast_run_id"])
            time.sleep(0.01)
        raise AssertionError("fixture forecast run did not settle")

    yield make
    supervisor.shutdown_drain(timeout_s=5)


def _forecast_output(engine, network, cutoff, series):
    """A ForecastOutput keyed by net_locations.id / net_products.id, as the lead confirmed."""
    with engine.connect() as conn:
        org = conn.scalar(sa.text("SELECT organization_id FROM networks WHERE id = :n"),
                          {"n": network.network_id})
        ids = {kind: dict(conn.execute(sa.text(
            f"SELECT external_id, id FROM {kind} WHERE dataset_version_id = :v"),
            {"v": network.dataset_version_id}).all()) for kind in ("net_locations", "net_products")}
    now, input_hash = datetime(2026, 11, 4, 12, tzinfo=UTC), "0" * 64
    rows = []
    for s in series:
        scope = SeriesScope(key=SeriesKey(
            organization_id=org, site_id=ids["net_locations"][s["location"]],
            product_id=ids["net_products"][s["product"]], target_type=s["target"]),
            unit="case", timezone="America/New_York", required=s["status"] == "AVAILABLE")
        common = {"result_id": uuid.uuid4(), "scope": scope, "status": s["status"],
                  "target_basis": s["basis"], "input_hash": input_hash, "generated_at": now,
                  "diagnostics": Diagnostics(observed_count=1, missing_count=0, proxy_fraction=0.0,
                                             reference_weekday_count=1, trailing_sample_count=1)}
        if s["status"] == "AVAILABLE":
            rows.append(ForecastSeriesResult(
                **common, actual_provider=ProviderIdentity(name=s["provider"]),
                fallback_used=s["fallback_reason"] is not None,
                fallback_reason=s["fallback_reason"],
                points=tuple(ForecastPoint(day=cutoff + timedelta(days=i + 1),
                                           central_estimate=c, estimate_kind="POINT")
                             for i, c in enumerate(s["central"]))))
        else:
            rows.append(ForecastSeriesResult(**common, errors=(StructuredError(
                code="INSUFFICIENT_HISTORY", message="too few observed days", category="DATA"),)))
    output = ForecastOutput(
        run_id=uuid.uuid4(), input_hash=input_hash, data_cutoff_date=cutoff, generated_at=now,
        completed_at=now, ready_for_publication=True, partial_scope=True,
        actual_providers=tuple(sorted({s["provider"] for s in series if s["provider"]})),
        warnings=(), series=tuple(rows))
    return org, output.model_dump(mode="json")


# --- helpers --------------------------------------------------------------------------------

def _network(engine, tmp_path, files=FILES, mode="PANTRY"):
    outcome = _import(engine, tmp_path, files, network=NewNetwork(
        name=f"Mini {uuid.uuid4().hex[:6]}", mode=mode, timezone="America/New_York"))
    assert outcome.ok, outcome.errors
    return outcome


def _scenario(engine, network, run_id, **options):
    options = {"transfer_mode": "HUB_ONLY", "planning_days": 2, **options}
    return create_scenario(SimpleNamespace(engine=engine), SCOPE, network.network_id,
                           ScenarioOptions(dataset_version_id=network.dataset_version_id,
                                           forecast_run_id=run_id, **options))


def _assumption(payload: ORInputV3, text: str) -> list[str]:
    return [a for a in payload.assumptions if text in a]


def _golden(payload: ORInputV3) -> ORInputV3:
    """The payload with its four install-specific ids fixed, so the hash is reproducible."""
    return payload.model_copy(update={
        "network_id": uuid.UUID(int=1), "organization_id": uuid.UUID(int=2),
        "dataset_version_id": uuid.UUID(int=3), "forecast_run_id": uuid.UUID(int=4)})


# --- the plan's tests -----------------------------------------------------------------------

def test_golden_mini_network_scenario_hash(engine, tmp_path, forecasts):
    network = _network(engine, tmp_path)
    scenario = _scenario(engine, network, forecasts(network))
    assert scenario.content_hash == operational_hash(scenario.payload)
    golden = _golden(scenario.payload)
    expected = json.loads((FIXTURE / "expected-scenario.json").read_text())
    assert golden.model_dump(mode="json") == expected
    assert operational_hash(golden) == (FIXTURE / "expected-hash.txt").read_text().strip()
    # Spot checks a reviewer can follow without the expected file:
    p = scenario.payload
    assert (p.snapshot_as_of, p.first_planning_date, p.planning_days) == (
        AS_OF, date(2026, 11, 5), 2)
    p1 = next(d for d in p.demand if (d.location_id, d.product_id) == ("P1", "RICE"))
    assert p1.central_literals == ("3", "2.5", "0", "4.2", "3", "1", "2")  # never rounded
    assert p1.targets == (3, 3, 0, 5, 3, 1, 2)  # each day rounded up (round_daily_targets)
    p2 = next(d for d in p.demand if (d.location_id, d.product_id) == ("P2", "RICE"))
    assert (p2.basis, p2.actual_provider, p2.fallback_reason) == (
        "sales", "MOVING_AVERAGE", "seasonal-naive history too short")
    assert sorted(b.id for b in p.batches) == ["H1/BEANS/B1", "H1/RICE/B1", "P1/RICE/B1",
                                               "P2/BEANS/B1"]
    assert {(r.from_location_id, r.to_location_id) for r in p.routes} == {
        ("H1", "P1"), ("H1", "P2"), ("H1", "P3")}  # HUB_ONLY
    assert _assumption(p, "P3 × BEANS")  # no available forecast: no target, never zero


def test_inbound_in_horizon_counted_once_not_also_on_hand(engine, tmp_path, forecasts):
    network = _network(engine, tmp_path)
    p = _scenario(engine, network, forecasts(network)).payload
    assert [(i.location_id, i.product_id, i.quantity, i.arrival_date) for i in p.inbound] == [
        ("P2", "RICE", 10, date(2026, 11, 6))]
    assert not [b for b in p.batches if (b.location_id, b.product_id) == ("P2", "RICE")]
    assert sum(b.quantity for b in p.batches if b.product_id == "RICE") == 124  # 120 + 4
    assert p.inbound_file_provided


def test_inbound_outside_horizon_excluded_and_listed(engine, tmp_path, forecasts):
    network = _network(engine, tmp_path)
    p = _scenario(engine, network, forecasts(network)).payload
    assert not [i for i in p.inbound if i.product_id == "BEANS"]
    [listed] = _assumption(p, "outside the seven-day horizon")
    assert "P1 × BEANS" in listed and "2026-11-20" in listed and "line 3" in listed


def test_blank_capacity_no_limit_with_assumption_text(engine, tmp_path, forecasts):
    network = _network(engine, tmp_path)
    p = _scenario(engine, network, forecasts(network)).payload
    receiving = {c.location_id: c.receiving for c in p.capacities}
    assert receiving == {"H1": None, "P1": 50, "P2": None, "P3": None}
    assert all(c.dispatch is None and c.storage is None for c in p.capacities)
    assert p.global_handling is None
    [text] = _assumption(p, "Receiving capacity")
    assert NO_LIMIT in text and "P2" in text and "P3" in text and "P1" not in text
    assert _assumption(p, "Dispatch, storage") and NO_LIMIT in _assumption(p, "Dispatch")[0]


def test_reserve_floors_default_zero_listed_as_assumption(engine, tmp_path, forecasts):
    network = _network(engine, tmp_path)
    run_id = forecasts(network)
    p = _scenario(engine, network, run_id).payload
    assert p.reserves == ()
    assert _assumption(p, "Reserve floors: 0")
    floor = ReserveV3(location_id="P1", product_id="RICE", floor=2)
    p = _scenario(engine, network, run_id, reserve_floors=(floor,)).payload
    assert p.reserves == (floor,)
    assert _assumption(p, "Reserve floors: 0 except P1 × RICE")


def test_cost_budget_off_by_default(engine, tmp_path, forecasts):
    network = _network(engine, tmp_path)
    run_id = forecasts(network)
    p = _scenario(engine, network, run_id).payload
    assert p.cost_budget_minor is None and _assumption(p, "Cost budget: off")
    p = _scenario(engine, network, run_id, cost_budget_minor=50_000).payload
    assert p.cost_budget_minor == 50_000 and not _assumption(p, "Cost budget: off")


def test_egp_freeze_blocked_until_attributes_resolved(engine, tmp_path, forecasts):
    unknown = FILES["locations"].replace("-82.9840,,0.15,0.12", "-82.9840,,,")
    network = _network(engine, tmp_path, {**FILES, "locations": unknown})
    run_id = forecasts(network)
    with pytest.raises(InputRejected) as blocked:
        _scenario(engine, network, run_id)
    assert blocked.value.code == "EGP_ATTRIBUTES_UNRESOLVED"
    assert blocked.value.details == {"locations": [
        {"location_id": "P3", "missing": ["poverty_rate", "snap_rate"]}]}
    rt = SimpleNamespace(engine=engine)
    set_location_attributes(rt, SCOPE, network.network_id, "P3",
                            LocationAttributesUpdate(excluded=True))
    p = _scenario(engine, network, run_id).payload
    assert sorted(v.location_id for v in p.vulnerability) == ["P1", "P2"]
    assert _assumption(p, "P3 excluded from EGP by the user")
    p1 = next(v for v in p.vulnerability if v.location_id == "P1")
    assert (p1.poverty_rate, p1.snap_rate, p1.source) == ("0.21", "0.18", "manual")


def test_retail_scenario_uses_seven_day_horizon(engine, tmp_path, forecasts):
    retail = {**FILES, "locations": FILES["locations"].replace(",hub,", ",distribution_center,")
              .replace(",pantry,", ",store,")}
    network = _network(engine, tmp_path, retail, mode="RETAIL")
    run_id = forecasts(network)
    p = _scenario(engine, network, run_id, planning_days=None).payload
    assert (p.mode, p.horizon_days, p.planning_days, p.policy) == ("RETAIL", 7, None, None)
    assert (p.retail_weights.w_exp, p.retail_weights.w_lost) == (1, 1)
    assert _assumption(p, "w_exp = 1, w_lost = 1")
    assert all(len(d.targets) == 7 for d in p.demand) and p.vulnerability == ()
    with pytest.raises(InputRejected) as error:
        _scenario(engine, network, run_id, planning_days=2)
    assert error.value.code == "WINDOW_AND_POLICY_ONLY_IN_PANTRY"


def test_donation_forecast_never_supply(engine, tmp_path, forecasts):
    network = _network(engine, tmp_path)
    p = _scenario(engine, network, forecasts(network)).payload
    assert {(d.location_id, d.product_id) for d in p.demand} == {("P1", "RICE"), ("P2", "RICE")}
    assert not [i for i in p.inbound if i.location_id == "P1"]  # the donation forecast is not
    assert sum(b.quantity for b in p.batches if b.location_id == "P1") == 4  # stock or arrival
    assert _assumption(p, "forecast, not confirmed")


def test_no_scheduled_deliveries_flag_when_no_inbound_file(engine, tmp_path, forecasts):
    network = _network(engine, tmp_path, {k: v for k, v in FILES.items() if k != "inbound"})
    p = _scenario(engine, network, forecasts(network)).payload
    assert p.inbound == () and not p.inbound_file_provided
    assert _assumption(p, "no scheduled deliveries provided")


# --- the request's checks -------------------------------------------------------------------

def test_scenario_is_stored_and_served_over_http(engine, tmp_path, forecasts):
    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.routers.forecasts import presenter, runtime

    network = _network(engine, tmp_path)
    run_id = forecasts(network)
    app = create_app()
    app.dependency_overrides[runtime] = lambda: SimpleNamespace(engine=engine)
    app.dependency_overrides[presenter] = lambda: SCOPE
    response = TestClient(app).post(f"/api/v1/networks/{network.network_id}/scenarios", json={
        "dataset_version_id": str(network.dataset_version_id), "forecast_run_id": str(run_id),
        "transfer_mode": "HUB_AND_PANTRY", "planning_days": 1})
    assert response.status_code == 201, response.text
    body = response.json()
    with engine.connect() as conn:
        row = conn.execute(sa.text(
            "SELECT network_id, dataset_version_id, forecast_run_id, content_hash, payload "
            "FROM planning_scenarios_v3 WHERE id = :id"), {"id": body["id"]}).one()
    assert (row.network_id, row.dataset_version_id, row.forecast_run_id) == (
        network.network_id, network.dataset_version_id, run_id)
    assert row.content_hash == body["content_hash"] == operational_hash(
        ORInputV3.model_validate(row.payload))
    assert body["payload"]["policy"]["lambda_percent"] == 100  # DEFAULT_PANTRY_POLICY frozen


def test_pantry_without_window_is_422(engine, tmp_path, forecasts):
    network = _network(engine, tmp_path)
    with pytest.raises(InputRejected) as error:
        _scenario(engine, network, forecasts(network), planning_days=None)
    assert error.value.code == "PLANNING_DAYS_REQUIRED"


def test_forecast_and_version_mismatches(engine, tmp_path, forecasts):
    network = _network(engine, tmp_path)
    run_id = forecasts(network)

    def refused(**options):
        with pytest.raises(AccessError) as error:
            _scenario(engine, network, **options)
        return error.value.code, error.value.status

    assert refused(run_id=uuid.uuid4()) == ("FORECAST_RUN_NOT_FOUND", 404)
    other = _network(engine, tmp_path / "other")
    assert refused(run_id=forecasts(other)) == ("FORECAST_RUN_NOT_FOUND", 404)  # other network
    assert refused(run_id=forecasts(network, dataset_id=uuid.uuid4())) == (
        "FORECAST_VERSION_MISMATCH", 409)
    assert refused(run_id=forecasts(network, cutoff=date(2026, 11, 3))) == (
        "FORECAST_VERSION_MISMATCH", 409)
    assert refused(run_id=forecasts(network, ready=False)) == (
        "FORECAST_NOT_PLANNING_READY", 409)
    with pytest.raises(AccessError) as missing:
        create_scenario(SimpleNamespace(engine=engine), SCOPE, uuid.uuid4(), ScenarioOptions(
            dataset_version_id=network.dataset_version_id, forecast_run_id=run_id,
            transfer_mode="HUB_ONLY", planning_days=2))
    assert (missing.value.code, missing.value.status) == ("NETWORK_NOT_FOUND", 404)


def test_new_scenario_on_an_older_version_is_409(engine, tmp_path, forecasts):
    first = _network(engine, tmp_path)
    run_id = forecasts(first)
    newer = _import(engine, tmp_path / "again", FILES, network=first.network_id)
    assert newer.ok and newer.dataset_version_id != first.dataset_version_id
    with pytest.raises(AccessError) as stale:
        _scenario(engine, first, run_id)
    assert (stale.value.code, stale.value.status) == ("STALE_DATASET_VERSION", 409)


def test_fractional_handling_units_cannot_be_frozen(engine, tmp_path, forecasts):
    products = FILES["products"].replace("RICE,Rice,case,,2", "RICE,Rice,case,,0.5")
    network = _network(engine, tmp_path, {**FILES, "products": products})
    with pytest.raises(InputRejected) as error:
        _scenario(engine, network, forecasts(network))
    assert error.value.code == "HANDLING_UNITS_NOT_WHOLE"
    assert error.value.details == {"products": ["RICE"]}


def test_profile_is_the_enrichment_job_profile():
    # The fixture job reuses the enrichment tests' short profile; its forecast budget is 3 s.
    assert dataclasses.asdict(PROFILE)["forecast_total_s"] == 3
