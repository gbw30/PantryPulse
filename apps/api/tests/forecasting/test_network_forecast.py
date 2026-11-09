# covers: V1-A08, V1-A12, V1-A23
"""W3-F03: forecasts for imported networks through forecast.v1 (V1-SPEC §6.1, §6.4; S7).

A Pantry network is imported through the real import path. Then submit_network_forecast
freezes a compact input, the production forecast.v1 registration runs it under a supervisor,
and its publisher writes the forecast_runs row that create_scenario reads.

History, as of 2026-11-04:

| series | days | what it pins |
|---|---|---|
| P1 × RICE (case) | 42, weekly 10 12 8 9 11 14 6 | seasonal naive repeats the last week |
| P1 × MILK (lb) | 42, the last 21 rows `sales` | the series is labeled sales |
| P2 × BEANS (case) | 20 of 4, blank 2 days ago | moving average (labeled fallback), mean 4 |
| P2 × RICE (case) | 10 | under 14 days: listed, no points, never zeros |
| P3 × RICE (case) | 20, every day blank | listed, no points |
| donation P1 × RICE | 21 of 3 | a donation forecast, never supply |
"""

import time
import uuid
from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic import command
from pydantic import ValidationError

import tests.integration.fake_driver as fake_driver
from app.repositories.forecast_history import HistoryRejected
from app.repositories.jobs import QueueRepository, TrustedScope, create_queue_engine
from app.schemas.v1_imports import NewNetwork
from app.schemas.v1_networks import BacktestScore, NetworkForecastRequest
from app.schemas.v1_planning import ScenarioOptions
from app.services.forecasting.backtest import backtest_series, baseline_fit, get_backtest
from app.services.forecasting.network import (
    get_forecast_run,
    list_forecast_runs,
    submit_network_forecast,
)
from app.services.jobs.contracts import TERMINAL_STATES, AttemptState
from app.services.jobs.registry import Registry
from app.services.networks.api import create_scenario
from app.services.presenter_access import AccessError
from app.workers.forecasting import REGISTRATION
from app.workers.supervisor import Supervisor, SupervisorConfig
from tests.enrichment.test_enrichment_job import PROFILE, QUIET
from tests.imports.test_import_postgres import _import
from tests.integration.wq_support import alembic_config, database_url, reset_schema

pytestmark = pytest.mark.integration
SCHEMA = "w3_forecast_network_test"
SESSION = TrustedScope(uuid.UUID(int=1), "local")  # the session's own organization
AS_OF = date(2026, 11, 4)
HORIZON = [AS_OF + timedelta(days=i) for i in range(1, 8)]
WEEK = (10, 12, 8, 9, 11, 14, 6)


def back(n: int) -> list[date]:
    return [AS_OF - timedelta(days=n - 1 - i) for i in range(n)]


def demand_csv() -> str:
    rows = ["location_id,product_id,date,quantity,basis"]
    rows += [f"P1,RICE,{d},{WEEK[i % 7]},demand" for i, d in enumerate(back(42))]
    rows += [f"P1,MILK,{d},{20 + i % 3},{'sales' if i >= 21 else 'demand'}"
             for i, d in enumerate(back(42))]
    rows += [f"P2,BEANS,{d},{'' if i == 17 else 4},demand" for i, d in enumerate(back(20))]
    rows += [f"P2,RICE,{d},5,demand" for d in back(10)]
    rows += [f"P3,RICE,{d},,demand" for d in back(20)]
    return "\n".join(rows) + "\n"


FILES = {
    "locations": (
        "location_id,name,type,street,city,state,zip,latitude,longitude,"
        "receiving_capacity_per_day,poverty_rate,snap_rate\n"
        "H1,North Hub,hub,301 S Monroe St,Tallahassee,FL,32301,30.4383,-84.2807,,,\n"
        "P1,Pantry One,pantry,201 E University Ave,Gainesville,FL,32601,29.6516,-82.3248,"
        ",0.21,0.18\n"
        "P2,Pantry Two,pantry,100 N Marion Ave,Lake City,FL,32055,30.1897,-82.6393,,0.30,0.25\n"
        "P3,Pantry Three,pantry,1 Main St,Ocala,FL,34471,29.1872,-82.1401,,0.25,0.20\n"),
    "products": "product_id,name,unit,unit_value_usd,handling_units_per_unit\n"
                "RICE,Rice,case,,1\nMILK,Milk,lb,,1\nBEANS,Beans,case,,1\n",
    "inventory": "location_id,product_id,batch_id,quantity,expiry_date,non_expiring,received_date\n"
                 "H1,RICE,B1,100,2026-11-30,,\nP1,RICE,B1,5,,true,\nP2,BEANS,B1,3,,true,\n",
    "demand_history": demand_csv(),
    "donation_history": "location_id,product_id,date,quantity,donor\n" + "".join(
        f"P1,RICE,{d},3,Grocer\n" for d in back(21)),
}


@contextmanager
def forecast_stack(schema: str, tmp):
    """A migrated schema with the production forecast.v1 registration under a supervisor."""
    url = database_url()
    reset_schema(url, schema)
    engine = create_queue_engine(url, schema=schema)
    with engine.begin() as conn:
        command.upgrade(alembic_config(conn), "head")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(fake_driver, "_behavior_for", lambda validated, step: QUIET)
        patch.setattr(fake_driver, "_with_behavior", lambda validated, step, b: validated)
        registry = Registry([REGISTRATION])
        queue = QueueRepository(engine, registry=registry, profile=PROFILE)
        supervisor = Supervisor(queue, registry, fake_driver.FakeDriver(registry=registry),
                                SupervisorConfig(registry_name="test", profile=PROFILE,
                                                 tick_s=0.02))
        assert supervisor.start()
        try:
            yield SimpleNamespace(engine=engine, queue=queue, supervisor=supervisor, tmp=tmp)
        finally:
            supervisor.shutdown_drain(timeout_s=5)
    engine.dispose()
    reset_schema(url, schema)


@pytest.fixture(scope="module")
def stack(tmp_path_factory):
    with forecast_stack(SCHEMA, tmp_path_factory.mktemp("imports")) as built:
        yield built


def import_network(stack, files=FILES, network=None):
    outcome = _import(stack.engine, stack.tmp, files, network=network or NewNetwork(
        name=f"Forecast {uuid.uuid4().hex[:6]}", mode="PANTRY", timezone="America/New_York"),
        as_of=AS_OF)
    assert outcome.ok, outcome.errors
    return outcome


def run(stack, network) -> uuid.UUID:
    accepted = submit_network_forecast(
        stack, SESSION, network.network_id,
        NetworkForecastRequest(dataset_version_id=network.dataset_version_id),
        f"forecast-{uuid.uuid4()}")
    with stack.engine.connect() as conn:
        org = conn.scalar(sa.text("SELECT organization_id FROM networks WHERE id = :n"),
                          {"n": network.network_id})
    end = time.monotonic() + 30
    while (job := stack.queue.get_job(TrustedScope(org, "test"), accepted.job_id)).state \
            not in TERMINAL_STATES:
        assert time.monotonic() < end, "forecast.v1 did not settle"
        stack.supervisor.tick()
        time.sleep(0.01)
    assert job.state == AttemptState.SUCCEEDED, job
    return accepted.job_id


@pytest.fixture(scope="module")
def published(stack):
    network = import_network(stack)
    job_id = run(stack, network)
    return SimpleNamespace(network=network, job_id=job_id,
                           run=get_forecast_run(stack, SESSION, network.network_id, job_id))


def series(run, location, product, kind="demand"):
    (row,) = [s for s in run.series
              if (s.location_id, s.product_id, s.kind) == (location, product, kind)]
    return row


def test_every_eligible_series_gets_seven_dated_points_with_actual_provider_and_fallback(
        published):
    run = published.run
    assert run.planning_ready
    assert run.data_cutoff_date == AS_OF
    assert run.dataset_version_id == published.network.dataset_version_id
    available = [s for s in run.series if s.status == "AVAILABLE"]
    assert {(s.location_id, s.product_id, s.kind) for s in available} == {
        ("P1", "RICE", "demand"), ("P1", "MILK", "demand"), ("P2", "BEANS", "demand"),
        ("P1", "RICE", "donation")}
    for s in available:
        assert [p.day for p in s.points] == HORIZON
        assert s.actual_provider.name in {"SEASONAL_NAIVE", "MOVING_AVERAGE"}
        assert all(p.p10 is None and p.p90 is None for p in s.points)  # baselines: no bands
    rice = series(run, "P1", "RICE")
    assert (rice.actual_provider.name, rice.fallback_used, rice.fallback_reason) == (
        "SEASONAL_NAIVE", False, None)
    assert [p.central_estimate for p in rice.points] == list(WEEK)  # the last observed week
    assert (rice.unit, rice.observed_count, rice.missing_count) == ("case", 42, 0)
    beans = series(run, "P2", "BEANS")
    assert beans.actual_provider.name == "MOVING_AVERAGE"
    assert beans.fallback_used and beans.fallback_reason
    assert [p.central_estimate for p in beans.points] == [4.0] * 7
    assert {p.estimate_kind for p in beans.points} == {"MEAN"}
    assert (beans.observed_count, beans.missing_count) == (19, 1)


def test_series_under_14_days_listed_ineligible_not_zero_filled(published, stack):
    short = series(published.run, "P2", "RICE")
    assert short.status == "INSUFFICIENT_DATA"
    assert short.points == () and short.actual_provider is None
    assert "14" in short.reason
    assert (short.observed_count, short.missing_count) == (10, 0)
    frozen = create_scenario(stack, SESSION, published.network.network_id, ScenarioOptions(
        dataset_version_id=published.network.dataset_version_id,
        forecast_run_id=published.job_id, transfer_mode="HUB_ONLY", planning_days=2)).payload
    assert ("P2", "RICE") not in {(d.location_id, d.product_id) for d in frozen.demand}
    assert any("No available forecast, so no demand target (not zero)" in a and "P2 × RICE" in a
               for a in frozen.assumptions)


def test_location_with_all_blank_history_listed_not_forecast(published):
    blank = series(published.run, "P3", "RICE")
    assert blank.status == "INSUFFICIENT_DATA"
    assert blank.points == ()
    assert (blank.observed_count, blank.missing_count) == (0, 20)
    assert "blank" in blank.reason


def test_sales_basis_carried_to_series_label(published, stack):
    assert series(published.run, "P1", "MILK").basis == "sales"
    assert series(published.run, "P1", "RICE").basis == "demand"
    assert series(published.run, "P1", "MILK").unit == "lb"
    frozen = create_scenario(stack, SESSION, published.network.network_id, ScenarioOptions(
        dataset_version_id=published.network.dataset_version_id,
        forecast_run_id=published.job_id, transfer_mode="HUB_ONLY", planning_days=2)).payload
    milk = next(d for d in frozen.demand if (d.location_id, d.product_id) == ("P1", "MILK"))
    assert milk.basis == "sales"


def test_donation_series_forecast_labeled_not_confirmed(published, stack):
    donation = series(published.run, "P1", "RICE", kind="donation")
    assert donation.status == "AVAILABLE"
    assert donation.basis is None
    assert [p.central_estimate for p in donation.points] == [3.0] * 7
    frozen = create_scenario(stack, SESSION, published.network.network_id, ScenarioOptions(
        dataset_version_id=published.network.dataset_version_id,
        forecast_run_id=published.job_id, transfer_mode="HUB_ONLY", planning_days=2)).payload
    assert any("Expected donations (forecast, not confirmed)" in a for a in frozen.assumptions)
    assert frozen.inbound == ()  # a forecast donation never becomes an arrival
    rice = next(d for d in frozen.demand if (d.location_id, d.product_id) == ("P1", "RICE"))
    assert rice.targets == WEEK  # demand alone: donations don't net it down


def test_create_scenario_accepts_a_published_network_run(published, stack):
    scenario = create_scenario(stack, SESSION, published.network.network_id, ScenarioOptions(
        dataset_version_id=published.network.dataset_version_id,
        forecast_run_id=published.job_id, transfer_mode="HUB_ONLY", planning_days=2))
    assert scenario.payload.forecast_run_id == published.job_id
    assert {(d.location_id, d.product_id, d.actual_provider) for d in scenario.payload.demand} == {
        ("P1", "MILK", "SEASONAL_NAIVE"), ("P1", "RICE", "SEASONAL_NAIVE"),
        ("P2", "BEANS", "MOVING_AVERAGE")}


def test_chronos_off_by_default(published, stack):
    with pytest.raises(ValidationError):  # the request can't ask for a model
        NetworkForecastRequest.model_validate(
            {"dataset_version_id": str(published.network.dataset_version_id),
             "strategy": "CHRONOS2"})
    with stack.engine.connect() as conn:
        job = conn.execute(sa.text(
            "SELECT handler_contract, input_package FROM compute_jobs WHERE job_id = :j"),
            {"j": published.job_id}).one()
    assert job.handler_contract == "forecast.v1"  # not forecast.chronos.v1
    assert job.input_package["input"]["network_forecast"]["policy"]["strategy"] == \
        "SEASONAL_NAIVE"
    providers = {s.actual_provider.name for s in published.run.series if s.actual_provider}
    assert providers <= {"SEASONAL_NAIVE", "MOVING_AVERAGE"}


def test_list_forecast_runs_newest_first(stack):
    network = import_network(stack)
    first = run(stack, network)
    again = submit_network_forecast(
        stack, SESSION, network.network_id,
        NetworkForecastRequest(dataset_version_id=network.dataset_version_id), "again")
    assert (again.job_id, again.replayed) == (first, True)  # same frozen input: no second job
    newer = import_network(stack, network=network.network_id)
    pending = submit_network_forecast(
        stack, SESSION, network.network_id,
        NetworkForecastRequest(dataset_version_id=newer.dataset_version_id), "newer")
    runs = list_forecast_runs(stack, SESSION, network.network_id).runs
    assert [r.job_id for r in runs] == [pending.job_id, first]
    assert runs[0].forecast_run_id is None and runs[0].state == AttemptState.QUEUED
    assert runs[0].dataset_version_id == newer.dataset_version_id
    assert runs[1].forecast_run_id == first and runs[1].state == AttemptState.SUCCEEDED
    assert runs[1].dataset_version_id == network.dataset_version_id
    while stack.queue.get_job(TrustedScope(_org(stack, network), "t"),
                              pending.job_id).state not in TERMINAL_STATES:
        stack.supervisor.tick()  # drain, so later tests start with an idle queue


def _org(stack, network):
    with stack.engine.connect() as conn:
        return conn.scalar(sa.text("SELECT organization_id FROM networks WHERE id = :n"),
                           {"n": network.network_id})


def test_reimport_makes_older_versions_and_runs_stale(stack):
    network = import_network(stack)
    old_run = run(stack, network)
    newer = import_network(stack, network=network.network_id)
    with pytest.raises(HistoryRejected) as stale:
        submit_network_forecast(stack, SESSION, network.network_id, NetworkForecastRequest(
            dataset_version_id=network.dataset_version_id), "stale")
    assert (stale.value.code, stale.value.status) == ("STALE_DATASET_VERSION", 409)
    with pytest.raises(AccessError, match="STALE_DATASET_VERSION"):
        create_scenario(stack, SESSION, network.network_id, ScenarioOptions(
            dataset_version_id=network.dataset_version_id, forecast_run_id=old_run,
            transfer_mode="HUB_ONLY", planning_days=2))
    assert newer.dataset_version_id != network.dataset_version_id


def test_unknown_network_and_foreign_run_are_404(published, stack):
    with pytest.raises(HistoryRejected) as missing:
        submit_network_forecast(stack, SESSION, uuid.uuid4(), NetworkForecastRequest(
            dataset_version_id=published.network.dataset_version_id), "nope")
    assert (missing.value.code, missing.value.status) == ("NETWORK_NOT_FOUND", 404)
    other = import_network(stack)
    with pytest.raises(HistoryRejected) as foreign:
        get_forecast_run(stack, SESSION, other.network_id, published.job_id)
    assert (foreign.value.code, foreign.value.status) == ("FORECAST_RUN_NOT_FOUND", 404)


def test_backtest_persisted_and_served_by_get_backtest(published, stack):
    """CR-w3-forecast-1 option B (ppv1_0014): the run's backtest is stored in
    forecast_runs.backtest when it publishes and served from that one row."""
    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.routers.forecasts import presenter, runtime

    result = get_backtest(stack, SESSION, published.job_id)
    assert (result.forecast_job_id, result.network_id) == (
        published.job_id, published.network.network_id)
    perfect = BacktestScore(origins_evaluated=4, wape_pct=Decimal("0.00"),
                            bias_pct=Decimal("0.00"), status="evaluated", scored_points=28)
    milk = backtest_series([Decimal(20 + i % 3) for i in range(42)], baseline_fit())
    short = backtest_series([Decimal(4)] * 20, baseline_fit())  # 20 days: under 35
    assert (milk.status, short.status) == ("evaluated", "not_evaluated_insufficient_history")
    assert [(s.location_id, s.product_id, s.basis, s.score) for s in result.series] == [
        ("P1", "MILK", "sales", milk), ("P1", "RICE", "demand", perfect),
        ("P2", "BEANS", "demand", short)]
    assert [(r.location_id, r.unit, r.series_count, r.score) for r in result.locations] == [
        ("P1", "case", 1, perfect), ("P1", "lb", 1, milk), ("P2", "case", 1, short)]
    assert [(r.location_id, r.product_id) for r in result.ineligible] == [
        ("P2", "RICE"), ("P3", "RICE")]
    assert "has 10" in result.ineligible[0].reason
    with stack.engine.connect() as conn:
        stored = conn.scalar(sa.text("SELECT backtest FROM forecast_runs WHERE id = :j"),
                             {"j": published.job_id})
    assert stored == result.model_dump(mode="json", exclude={"forecast_job_id", "network_id"})
    app = create_app()
    app.dependency_overrides[runtime] = lambda: stack
    app.dependency_overrides[presenter] = lambda: SESSION
    client = TestClient(app)
    response = client.get(f"/api/v1/forecasts/{published.job_id}/backtest")
    assert (response.status_code, response.json()) == (200, result.model_dump(mode="json"))
    response = client.get(f"/api/v1/forecasts/{uuid.uuid4()}/backtest")
    assert response.status_code == 404 and "FORECAST_RUN_NOT_FOUND" in response.text
