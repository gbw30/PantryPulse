# covers: V1-A02, V1-A05
"""The local seed loads both sample networks through the importer, on PostgreSQL (W3-P04).

Each test drives the seed exactly as `scripts/local_bootstrap.py` does: one ORM transaction
that has already inserted the local organization, then `ensure_samples`. Never skipped in CI."""

import dataclasses
import socket
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from alembic import command
from sqlalchemy.orm import Session

from app.repositories.jobs import TrustedScope, create_queue_engine
from app.schemas.v1_imports import NewNetwork
from app.schemas.v1_planning import ScenarioOptions
from app.services import samples
from app.services.networks.api import create_scenario
from app.services.samples import pantry, retail
from scripts import seed_local
from tests.imports.test_import_postgres import FILES, _import
from tests.integration.wq_support import alembic_config, database_url, reset_schema
from tests.networks import test_build_scenario as build_scenario
from tests.networks.test_build_scenario import forecasts  # noqa: F401 (fixture)
from tests.samples.rules import rows

pytestmark = pytest.mark.integration
SCHEMA = "w3_samples_seed_test"
TODAY = date(2026, 11, 9)
SCOPE = TrustedScope(uuid.UUID(int=1), "local")
NAMES = (pantry.NAME, retail.NAME)
VERSION_TABLES = ("net_locations", "net_products", "net_batches", "net_demand_history",
                  "net_donation_history", "net_inbound", "net_routes")


@pytest.fixture(scope="module")
def engine():
    url = database_url()
    reset_schema(url, SCHEMA)
    eng = create_queue_engine(url, schema=SCHEMA)
    with eng.begin() as conn:
        command.upgrade(alembic_config(conn), "head")

    @sa.event.listens_for(eng, "begin")
    def bounded_lock_waits(connection):
        # A publish blocked by the seed's own open transaction must fail, not hang the suite.
        connection.exec_driver_sql("SET LOCAL lock_timeout = '30s'")

    yield eng
    eng.dispose()
    reset_schema(url, SCHEMA)


@pytest.fixture
def sample_sized_forecasts(monkeypatch):
    """The borrowed fixture job caps its payload for the 2-product mini network; a sample's
    forecast (up to 1,000 series) needs more. Request this before `forecasts`."""
    monkeypatch.setattr(build_scenario, "FIXTURE_FORECAST", dataclasses.replace(
        build_scenario.FIXTURE_FORECAST, max_input_bytes=50_000_000,
        max_output_bytes=50_000_000))


@pytest.fixture
def db(engine):
    with engine.begin() as conn:
        conn.execute(sa.text("TRUNCATE organizations CASCADE"))
    return engine


def seed(engine, today: date) -> samples.SeedReport:
    """As `local_bootstrap.run`: the seed's own transaction holds the organization insert."""
    with Session(engine) as session, session.begin():
        seed_local.ensure_local_organization(session)
        return samples.ensure_samples(session, today)


def sample_versions(engine) -> dict[str, list[tuple]]:
    with engine.connect() as conn:
        found = conn.execute(sa.text(
            "SELECT n.name, n.id, n.is_sample, v.id, v.as_of_date FROM networks n "
            "JOIN dataset_versions v ON v.network_id = n.id WHERE n.is_sample "
            "ORDER BY n.name, v.as_of_date")).all()
    versions: dict[str, list[tuple]] = {}
    for name, network_id, is_sample, version_id, as_of in found:
        versions.setdefault(name, []).append((network_id, is_sample, version_id, as_of))
    return versions


def fingerprint(engine, version_id) -> dict[str, str]:
    """Every row of one dataset version, plus every frozen scenario, as md5 per table."""
    with engine.connect() as conn:
        prints = {t: conn.scalar(sa.text(
            f"SELECT md5(coalesce(string_agg(t::text, '|' ORDER BY t::text), '')) FROM {t} t "
            "WHERE dataset_version_id = :v"), {"v": version_id}) for t in VERSION_TABLES}
        for table in ("dataset_versions", "networks", "planning_scenarios_v3"):
            prints[table] = conn.scalar(sa.text(
                f"SELECT md5(coalesce(string_agg(t::text, '|' ORDER BY t::text), '')) "
                f"FROM {table} t"))
    return prints


def test_first_start_loads_both_samples(db):
    report = seed(db, TODAY)
    assert report.loaded == NAMES
    versions = sample_versions(db)
    assert sorted(versions) == sorted(NAMES)
    for name in NAMES:
        [(network_id, is_sample, version_id, as_of)] = versions[name]
        assert is_sample and as_of == TODAY
    with db.connect() as conn:
        counts = dict(conn.execute(sa.text(
            "SELECT n.mode, count(*) FROM net_locations l JOIN dataset_versions v "
            "ON v.id = l.dataset_version_id JOIN networks n ON n.id = v.network_id "
            "GROUP BY n.mode")).all())
        assert counts == {"PANTRY": 9, "RETAIL": 21}
        # The seed queues no enrichment: the samples have coordinates and sample rates.
        assert conn.scalar(sa.text(
            "SELECT count(*) FROM compute_jobs WHERE handler_contract = 'enrichment.v1'")) == 0


def test_second_start_loads_nothing(db):
    seed(db, TODAY)
    assert seed(db, TODAY).loaded == ()
    assert seed(db, TODAY + timedelta(days=7)).loaded == ()  # 7 days old is still fresh
    assert {name: len(v) for name, v in sample_versions(db).items()} == {n: 1 for n in NAMES}
    with db.connect() as conn:
        assert conn.scalar(sa.text("SELECT count(*) FROM networks")) == 2


def test_new_freshly_dated_version_when_newest_older_than_7_days(db):
    seed(db, TODAY)
    before = sample_versions(db)
    later = TODAY + timedelta(days=8)
    assert seed(db, later).loaded == NAMES
    after = sample_versions(db)
    for name in NAMES:
        [first, second] = after[name]
        assert first == before[name][0]
        assert second[0] == first[0] and second[1] is True  # same network, still a sample
        assert second[3] == later
    assert seed(db, later).loaded == ()


def test_older_versions_and_results_untouched(db, sample_sized_forecasts, forecasts):  # noqa: F811
    seed(db, TODAY)
    [(network_id, _, version_id, as_of)] = sample_versions(db)[pantry.NAME]
    scenario = _freeze(db, forecasts, pantry.pantry_sample(TODAY), network_id, version_id)
    before = fingerprint(db, version_id)
    seed(db, TODAY + timedelta(days=8))
    after = fingerprint(db, version_id)
    assert {t: after[t] for t in VERSION_TABLES} == {t: before[t] for t in VERSION_TABLES}
    assert after["planning_scenarios_v3"] == before["planning_scenarios_v3"]
    with db.connect() as conn:
        assert conn.scalar(sa.text(
            "SELECT content_hash FROM planning_scenarios_v3 WHERE id = :s"),
            {"s": scenario.id}) == scenario.content_hash
        assert conn.scalar(sa.text("SELECT as_of_date FROM dataset_versions WHERE id = :v"),
                           {"v": version_id}) == as_of


def test_duplicate_sample_names_do_not_stop_the_seed(db):
    # Two Pantry sample networks (e.g. left by an older racing seed): the freshest one decides.
    samples._import(db, pantry.pantry_sample(TODAY - timedelta(days=10)), None)
    samples._import(db, pantry.pantry_sample(TODAY), None)
    before = sample_versions(db)[pantry.NAME]
    assert seed(db, TODAY).loaded == (retail.NAME,)
    assert sample_versions(db)[pantry.NAME] == before  # the stale duplicate isn't re-imported
    assert seed(db, TODAY).loaded == ()


def test_user_network_named_like_a_sample_is_left_alone(db, tmp_path):
    named = NewNetwork(name=pantry.NAME, mode="PANTRY", timezone="America/New_York")
    assert _import(db, tmp_path, FILES, network=named).ok
    assert seed(db, TODAY).loaded == NAMES
    with db.connect() as conn:
        found = conn.execute(sa.text(
            "SELECT n.is_sample, count(v.id) FROM networks n JOIN dataset_versions v "
            "ON v.network_id = n.id WHERE n.name = :n GROUP BY n.id, n.is_sample "
            "ORDER BY n.is_sample"), {"n": pantry.NAME}).all()
    assert [tuple(r) for r in found] == [(False, 1), (True, 1)]


@pytest.mark.parametrize("stale", [False, True], ids=["empty", "stale"])
def test_concurrent_seeds_load_each_sample_once(db, monkeypatch, stale):
    if stale:
        seed(db, TODAY - timedelta(days=8))
    # Hold each import until both seeds are past their freshness check (the race window). A seed
    # that waits for the other one, as it must, never arrives, so the barrier times out.
    barrier = threading.Barrier(2, timeout=3)
    real_import = samples._import

    def gated(*args):
        try:
            barrier.wait()
        except threading.BrokenBarrierError:
            pass
        real_import(*args)

    monkeypatch.setattr(samples, "_import", gated)
    with ThreadPoolExecutor(2) as pool:
        reports = [f.result() for f in [pool.submit(seed, db, TODAY) for _ in range(2)]]
    assert sorted(r.loaded for r in reports) == [(), NAMES]
    assert {name: len(v) for name, v in sample_versions(db).items()} == {
        n: 1 + stale for n in NAMES}
    with db.connect() as conn:
        assert conn.scalar(sa.text("SELECT count(*) FROM networks")) == 2


def test_no_outbound_network_calls(db, monkeypatch):
    attempts = []

    def refuse(*args, **kwargs):
        attempts.append((args, kwargs))
        raise OSError("outbound network call refused by the test")

    # The test database connects through libpq (C sockets), so only Python sockets stop.
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket.socket, "connect_ex", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    assert seed(db, TODAY).loaded == NAMES
    assert attempts == []  # recorded, so a call the seed catches and ignores still fails here


def test_never_resets(db, tmp_path):
    user = _import(db, tmp_path, FILES)
    assert user.ok, user.errors
    before = fingerprint(db, user.dataset_version_id)
    seed(db, TODAY)
    seed(db, TODAY + timedelta(days=8))
    after = fingerprint(db, user.dataset_version_id)
    assert {t: after[t] for t in VERSION_TABLES} == {t: before[t] for t in VERSION_TABLES}
    with db.connect() as conn:
        assert conn.execute(sa.text("SELECT is_sample FROM networks WHERE id = :n"),
                            {"n": user.network_id}).scalar_one() is False
        assert conn.scalar(sa.text("SELECT count(*) FROM networks")) == 3
    source = " ".join(p.read_text(encoding="utf-8").upper() for p in Path(
        samples.__file__).parent.glob("*.py"))
    assert not any(word in source for word in ("DELETE ", "TRUNCATE", "DROP ", "UPDATE "))


def test_each_sample_freezes_cleanly(db, sample_sized_forecasts, forecasts):  # noqa: F811
    seed(db, TODAY)
    versions = sample_versions(db)
    for sample in (pantry.pantry_sample(TODAY), retail.retail_sample(TODAY)):
        [(network_id, _, version_id, _)] = versions[sample.name]
        payload = _freeze(db, forecasts, sample, network_id, version_id).payload
        receivers = {loc["location_id"] for loc in rows(sample, "locations")
                     if loc["type"] in ("pantry", "store")}
        # Every receiver has a route from its hub/DC inside 150 miles and 7 travel days.
        assert {r.to_location_id for r in payload.routes} == receivers
        assert not [a for a in payload.assumptions if "left out" in a or "No available" in a]
        assert len(payload.demand) == len(receivers) * len(rows(sample, "products"))
        if sample.mode == "PANTRY":
            assert {v.location_id for v in payload.vulnerability} == receivers


def _freeze(engine, forecasts, sample, network_id, version_id):  # noqa: F811
    """A fixture forecast for every receiver × product (last week's history repeated), then
    a frozen scenario through the real create_scenario."""
    history: dict[tuple[str, str], list[float]] = {}
    for row in rows(sample, "demand_history"):
        history.setdefault((row["location_id"], row["product_id"]), []).append(
            float(row["quantity"] or 0))
    basis = "REQUESTED" if sample.mode == "PANTRY" else "FULFILLED_PROXY"
    series = [{"location": loc, "product": prod, "target": "DEMAND", "status": "AVAILABLE",
               "basis": basis, "provider": "SEASONAL_NAIVE", "fallback_reason": None,
               "central": values[-7:]} for (loc, prod), values in sorted(history.items())]
    network = SimpleNamespace(network_id=network_id, dataset_version_id=version_id)
    run_id = forecasts(network, cutoff=sample.as_of_date, series=series)
    options: dict[str, object] = {"transfer_mode": "HUB_ONLY"}
    if sample.mode == "PANTRY":
        options["planning_days"] = 2
    return create_scenario(SimpleNamespace(engine=engine), SCOPE, network_id,
                           ScenarioOptions(dataset_version_id=version_id,
                                           forecast_run_id=run_id, **options))
