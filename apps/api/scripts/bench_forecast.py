"""Spike S7 (W3-F01, V1-SPEC §12 item 7): forecast and backtest volume at the series envelope.

Synthetic, seeded history: N series × D days, weekly pattern with noise and ~5 % blank days
(blank = unknown, never zero). Three parts, each run in its own process so peak RSS is its own:

  existing  the current forecast.v1 path (per-day DemandRevision → prepare → validate_input →
            forecast → ForecastOutput) on a sample, extrapolated linearly to N
  compact   per-series value arrays through the same adapters (seasonal naive, then the moving
            average) plus the 4-origin backtest, ForecastOutput built, serialized and re-read
  db        the compact run's output written to a scratch schema of a *_test database:
            one forecast_runs-shaped JSONB row plus one backtest row per series
  built     the shipped W3-F03/F05 code (W3-F06): network.validate_frozen, compute,
            build_output and build_backtest, sized against forecast.v1's byte bounds, then the
            danger ranking (danger.ranking.project_lines + danger_ranking) over one dated lot
            per series
  lock      forecast.v1 at N series through the real queue, supervisor and publisher in a
            scratch schema of a *_test database (the step runs in process, through the
            integration tests' fake driver): the publisher's prepare, outside the queue lock,
            and the lock itself, held from _lock_claimed to COMMIT (verifier F1)
  freeze    the freeze's real history aggregate (network._history) over N × D demand rows in
            a scratch schema of a *_test database: the submit request's own SQL time

Usage (from apps/api):
  uv run --frozen python scripts/bench_forecast.py --part compact --series 50000
  uv run --frozen python scripts/bench_forecast.py --part existing --series 50000 --sample 500
  uv run --frozen python scripts/bench_forecast.py --part db --series 50000   # PP_TEST_DATABASE_URL
  uv run --frozen python scripts/bench_forecast.py --part built --series 50000
  uv run --frozen python scripts/bench_forecast.py --part freeze --series 50000  # same URL
  uv run --frozen python scripts/bench_forecast.py --part lock --series 50000    # same URL
Prints one JSON object. Synthetic data: timings only, never accuracy evidence.
"""

import argparse
import json
import os
import platform
import random
import resource
import subprocess
import sys
import time
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4, uuid5

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

CUTOFF = date(2026, 11, 4)
ORG, DATASET = UUID(int=1), UUID(int=2)
CEILING_S = 300  # forecast operation ceiling (forecast 270/300 s)


def history(n: int, days: int, seed: int = 7) -> list[list[int | None]]:
    rng = random.Random(seed)
    rows = []
    for _ in range(n):
        base, weekly = rng.uniform(0, 60), [rng.uniform(0.5, 1.5) for _ in range(7)]
        rows.append([None if rng.random() < 0.05
                     else max(0, round(base * weekly[d % 7] + rng.gauss(0, 3)))
                     for d in range(days)])
    return rows


def peak_rss_mb() -> float:
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 1)


def compact(n: int, days: int) -> tuple[dict, str]:
    from app.services.forecasting.adapters.base import ProviderError
    from app.services.forecasting.backtest import baseline_fit, location_rollups, scored_set
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

    timings, t = {}, time.perf_counter()
    data = history(n, days)
    timings["generate_s"] = time.perf_counter() - t
    locations = [uuid5(DATASET, f"L{i}") for i in range(100)]
    products = [uuid5(DATASET, f"P{i}") for i in range(max(1, n // 100))]
    t = time.perf_counter()
    window = 42  # the most any method reads: MA fallback at origin 4 (28 + 14 days)
    frozen = {"series": [{"l": i % 100, "p": i // 100, "v": v[-window:],
                          "observed": sum(x is not None for x in v), "days": len(v)}
                         for i, v in enumerate(data)]}
    frozen_json = json.dumps(frozen, separators=(",", ":"))
    full_json = json.dumps([v for v in data], separators=(",", ":"))
    timings["freeze_s"] = time.perf_counter() - t

    fit = baseline_fit()
    t = time.perf_counter()
    forecasts, fallbacks, failed = [], 0, 0
    for series in frozen["series"]:
        values = [None if x is None else Decimal(x) for x in series["v"]]
        try:
            forecasts.append(fit(values))
            fallbacks += any(x is None for x in values[-7:])
        except ProviderError:
            forecasts.append(None)
            failed += 1
    timings["forecast_s"] = time.perf_counter() - t

    t = time.perf_counter()
    sets = [scored_set([None if x is None else Decimal(x) for x in s["v"]], fit)
            for s in frozen["series"]]
    rollups = location_rollups((str(s["l"]), "case", x)
                               for s, x in zip(frozen["series"], sets, strict=True))
    timings["backtest_s"] = time.perf_counter() - t

    t = time.perf_counter()
    now, rows = datetime.now(UTC), []
    for i, (series, points) in enumerate(zip(frozen["series"], forecasts, strict=True)):
        scope = SeriesScope(key=SeriesKey(organization_id=ORG, site_id=locations[series["l"]],
                                          product_id=products[series["p"]], target_type="DEMAND"),
                            unit="case", timezone="America/New_York")
        common = dict(result_id=uuid5(DATASET, str(i)), scope=scope, target_basis="REQUESTED",
                      input_hash="0" * 64, generated_at=now,
                      diagnostics=Diagnostics(observed_count=series["observed"],
                                              missing_count=series["days"] - series["observed"],
                                              proxy_fraction=0.0, reference_weekday_count=0,
                                              trailing_sample_count=0))
        if points is None:
            rows.append(ForecastSeriesResult(**common, status="INSUFFICIENT_DATA", errors=(
                StructuredError(code="INSUFFICIENT_DATA", message="too few", category="DATA"),)))
            continue
        rows.append(ForecastSeriesResult(
            **common, status="AVAILABLE", actual_provider=ProviderIdentity(name="SEASONAL_NAIVE"),
            points=tuple(ForecastPoint(day=CUTOFF + timedelta(days=d + 1),
                                       central_estimate=float(p), estimate_kind="POINT")
                         for d, p in enumerate(points))))
    output = ForecastOutput(run_id=uuid4(), input_hash="0" * 64, data_cutoff_date=CUTOFF,
                            generated_at=now, completed_at=now,
                            ready_for_publication=failed == 0, partial_scope=False,
                            actual_providers=("SEASONAL_NAIVE",), warnings=(), series=tuple(rows))
    timings["output_build_s"] = time.perf_counter() - t
    t = time.perf_counter()
    output_json = output.model_dump_json()
    timings["output_dump_s"] = time.perf_counter() - t
    t = time.perf_counter()
    ForecastOutput.model_validate_json(output_json)
    timings["output_reread_s"] = time.perf_counter() - t  # what create_scenario pays per freeze
    timings = {k: round(v, 2) for k, v in timings.items()}
    compute = sum(v for k, v in timings.items() if k not in ("generate_s", "output_reread_s"))
    return {
        "series": n, "days": days, "timings": timings, "compute_s": round(compute, 2),
        "within_ceiling": compute < CEILING_S,
        "frozen_input_mb_42_day_window": round(len(frozen_json) / 1e6, 2),
        "frozen_input_mb_full_history_values_only": round(len(full_json) / 1e6, 2),
        "output_json_mb": round(len(output_json) / 1e6, 2),
        "series_failed": failed, "series_with_gap_in_last_week": fallbacks,
        "backtest_rows": len(sets), "location_rollups": len(rollups),
    }, output_json


def existing(n: int, days: int, sample: int) -> dict:
    from app.services.forecasting.adapters.seasonal_naive import SeasonalNaiveAdapter
    from app.services.forecasting.preparation import prepare, validate_input
    from app.services.forecasting.schemas import (
        ForecastPolicy,
        HistoryBundle,
        SeriesKey,
        SeriesScope,
    )
    from app.services.forecasting.service import forecast

    data = history(sample, days)
    t = time.perf_counter()
    scopes, rows = [], []
    for i, values in enumerate(data):
        key = SeriesKey(organization_id=ORG, site_id=uuid5(DATASET, f"L{i % 100}"),
                        product_id=uuid5(DATASET, f"P{i // 100}"), target_type="DEMAND")
        scopes.append(SeriesScope(key=key, unit="case", timezone="America/New_York"))
        for d, v in enumerate(values):
            if v is None:
                continue
            day = CUTOFF - timedelta(days=days - 1 - d)
            rows.append({"source": {"organization_id": str(ORG), "dataset_id": str(DATASET),
                                    "logical_key": f"{i}:{day}", "revision_id": str(uuid4()),
                                    "revision": 1, "recorded_at": "2026-11-04T00:00:00Z"},
                         "key": key.model_dump(mode="json"), "day": str(day),
                         "requested_units": v, "fulfilled_units": None, "unmet_units": None,
                         "source_classification": "OBSERVED"})
    bundle = HistoryBundle(organization_id=ORG, dataset_id=DATASET, scope=tuple(scopes),
                           demand=tuple(rows))
    build = time.perf_counter() - t
    policy = ForecastPolicy(policy_version="v1-network", sparse_window_days=14,
                            sparse_min_samples=3, allow_fallback=True)
    t = time.perf_counter()
    inputs = prepare(bundle, data_cutoff_date=CUTOFF,
                     snapshot_as_of=datetime(2026, 11, 5, tzinfo=UTC), policy=policy)
    prep = time.perf_counter() - t
    t = time.perf_counter()
    validate_input(inputs)
    validate = time.perf_counter() - t
    t = time.perf_counter()
    output = forecast(inputs, adapter=SeasonalNaiveAdapter())
    run = time.perf_counter() - t
    input_mb = len(inputs.model_dump_json()) / 1e6
    output_mb = len(output.model_dump_json()) / 1e6
    # The handler revalidates the frozen input at admission, in the step, and twice at publish.
    per_series = (build + prep + 4 * validate + run) / sample
    return {
        "sample_series": sample, "days": days, "history_rows": len(rows),
        "timings_sample": {k: round(v, 2) for k, v in dict(
            build_bundle_s=build, prepare_s=prep, validate_input_s=validate,
            forecast_s=run).items()},
        "input_mb_sample": round(input_mb, 2), "output_mb_sample": round(output_mb, 2),
        "extrapolated_to": n,
        "extrapolated_compute_s_excl_backtest": round(per_series * n, 1),
        "extrapolated_input_mb": round(input_mb * n / sample, 1),
        "extrapolated_output_mb": round(output_mb * n / sample, 1),
        "worker_bounds": "forecast.v1: <= 800 series, <= 60,000 observations, 16 MB in, 4 MB out",
    }


def db(n: int, days: int) -> dict:
    import sqlalchemy as sa

    url = os.environ.get("PP_TEST_DATABASE_URL", "")
    if not url.rsplit("/", 1)[-1].split("?")[0].endswith("_test"):
        raise SystemExit("PP_TEST_DATABASE_URL must name a *_test database")
    result, output_json = compact(n, days)
    engine = sa.create_engine(url)
    schema = "bench_s7_test"
    with engine.begin() as conn:
        conn.execute(sa.text(f"DROP SCHEMA IF EXISTS {schema} CASCADE; CREATE SCHEMA {schema}"))
        conn.execute(sa.text(f"CREATE TABLE {schema}.runs (id uuid PRIMARY KEY, output jsonb)"))
        conn.execute(sa.text(
            f"CREATE TABLE {schema}.scores (id uuid PRIMARY KEY, location_id uuid, product_id uuid,"
            " series_kind text, method text, evaluated bool, scored_points int,"
            " wape numeric(12,6), bias numeric(12,6))"))
    try:
        with engine.begin() as conn:
            t = time.perf_counter()
            conn.execute(sa.text(f"INSERT INTO {schema}.runs VALUES (:i, CAST(:o AS jsonb))"),
                         {"i": uuid4(), "o": output_json})
            run_s = time.perf_counter() - t
            t = time.perf_counter()
            conn.execute(sa.text(f"INSERT INTO {schema}.scores VALUES (:i, :l, :p, 'demand', "
                                 "'SEASONAL_NAIVE', true, 28, 12.5, -1.5)"),
                         [{"i": uuid4(), "l": uuid4(), "p": uuid4()} for _ in range(n)])
            scores_s = time.perf_counter() - t
        with engine.connect() as conn:
            size = {t: conn.scalar(sa.text(f"SELECT pg_total_relation_size('{schema}.{t}')"))
                    for t in ("runs", "scores")}
            t = time.perf_counter()
            conn.execute(sa.text(f"SELECT output FROM {schema}.runs")).one()
            read_s = time.perf_counter() - t
    finally:
        with engine.begin() as conn:
            conn.execute(sa.text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        engine.dispose()
    result.update(db={
        "run_row_insert_s": round(run_s, 2), "run_row_read_s": round(read_s, 2),
        "backtest_rows_insert_s": round(scores_s, 2), "rows_written": 1 + n,
        "run_row_storage_mb": round(size["runs"] / 1e6, 1),
        "backtest_rows_storage_mb": round(size["scores"] / 1e6, 1)})
    return result


def network_input(n: int, days: int):
    """N synthetic demand series over 100 locations, as the freeze would encode them."""
    from app.services.forecasting.network import (
        WINDOW_DAYS,
        FrozenSeries,
        NetworkForecastInput,
        NetworkPolicy,
        _hash,
    )
    data = history(n, days)
    locations = tuple((uuid5(DATASET, f"L{i}"), f"L{i:03d}") for i in range(100))
    products = tuple((uuid5(DATASET, f"P{i}"), f"P{i:04d}", "case")
                     for i in range(max(1, -(-n // 100))))
    inputs = NetworkForecastInput(
        organization_id=ORG, network_id=uuid5(DATASET, "network"), dataset_id=DATASET,
        data_cutoff_date=CUTOFF, history_end=CUTOFF, timezone="America/New_York",
        policy=NetworkPolicy(), locations=locations, products=products, input_hash="",
        series=tuple(FrozenSeries(location=i % 100, product=i // 100, kind="demand",
                                  basis="demand", values=tuple(v[-WINDOW_DAYS:]),
                                  observed=sum(x is not None for x in v),
                                  missing=sum(x is None for x in v))
                     for i, v in enumerate(data)))
    return inputs.model_copy(update={"input_hash": _hash(inputs)})


def built(n: int, days: int) -> dict:
    from app.schemas.v1_planning import BatchV3
    from app.services.danger.ranking import danger_ranking, project_lines
    from app.services.forecasting.network import (
        build_backtest,
        build_output,
        compute,
        validate_frozen,
    )
    from app.workers.forecasting import REGISTRATION
    timings, t = {}, time.perf_counter()  # the freeze's Python side; its SQL is not timed here
    inputs = network_input(n, days)
    locations, products = inputs.locations, inputs.products
    input_json = json.dumps({"network_forecast": inputs.model_dump(mode="json")},
                            separators=(",", ":"))
    timings["generate_and_freeze_python_s"] = time.perf_counter() - t
    t = time.perf_counter()  # admission, the step child and the publisher each pay this
    validated = validate_frozen(json.loads(input_json)["network_forecast"])
    timings["validate_input_s"] = time.perf_counter() - t
    t = time.perf_counter()
    step_json = json.dumps({"network_output": compute(validated)}, separators=(",", ":"))
    timings["step_compute_s"] = time.perf_counter() - t
    t = time.perf_counter()  # the publisher's prepare, outside the queue lock since verifier F1
    package, run_id = json.loads(step_json)["network_output"], uuid4()
    output = build_output(validated, package, run_id)
    output_json = output.model_dump_json()
    timings["publish_build_output_s"] = time.perf_counter() - t
    t = time.perf_counter()
    backtest_json = json.dumps(build_backtest(validated, package, run_id))
    timings["publish_build_backtest_s"] = time.perf_counter() - t
    t = time.perf_counter()
    batches = [BatchV3(id=f"{locations[s.location][1]}/{products[s.product][1]}/B1",
                       location_id=locations[s.location][1], product_id=products[s.product][1],
                       quantity=20 + i % 40, expiry_date=CUTOFF + timedelta(days=1 + i % 10),
                       non_expiring=False)
               for i, s in enumerate(validated.series)]
    rows = danger_ranking(project_lines(validated, output, batches, []), "RETAIL")
    timings["danger_ranking_s"] = time.perf_counter() - t
    timings = {k: round(v, 2) for k, v in timings.items()}
    # workers/forecasting.py validates the frozen input 4 times: admission, the step, the
    # publisher's validate and its prepare, which then builds the run outside the lock.
    publish = timings["publish_build_output_s"] + timings["publish_build_backtest_s"]
    job = 4 * timings["validate_input_s"] + timings["step_compute_s"] + publish
    prepare = timings["validate_input_s"] + publish
    statuses = [r["status"] for r in json.loads(step_json)["network_output"]["series"]]
    return {
        "series": n, "days": days, "timings": timings,
        "forecast_job_compute_s": round(job, 2), "ceiling_s": CEILING_S,
        "within_ceiling": job < CEILING_S,
        "publish_prepare_s_outside_lock": round(prepare, 2),
        "frozen_input_mb": round(len(input_json) / 1e6, 2),
        "max_input_mb": REGISTRATION.max_input_bytes / 1e6,
        "step_output_mb": round(len(step_json) / 1e6, 2),
        "max_output_mb": REGISTRATION.max_output_bytes / 1e6,
        "stored_output_json_mb": round(len(output_json) / 1e6, 2),
        "stored_backtest_json_mb": round(len(backtest_json) / 1e6, 2),
        "series_available": statuses.count("AVAILABLE"),
        "series_insufficient": statuses.count("INSUFFICIENT_DATA"),
        "danger_rows": len(rows),
    }


def lock(n: int, days: int) -> dict:
    import pytest
    import sqlalchemy as sa
    from alembic import command

    import tests.integration.fake_driver as fake_driver
    from app.repositories.jobs import QueueRepository, TrustedScope, create_queue_engine
    from app.services.jobs.contracts import PRODUCTION_PROFILE, TERMINAL_STATES
    from app.services.jobs.registry import Registry
    from app.workers.forecasting import REGISTRATION
    from app.workers.supervisor import Supervisor, SupervisorConfig
    from tests.integration.wq_support import alembic_config, reset_schema

    url = os.environ.get("PP_TEST_DATABASE_URL", "")
    if not url.rsplit("/", 1)[-1].split("?")[0].endswith("_test"):
        raise SystemExit("PP_TEST_DATABASE_URL must name a *_test database")
    payload = {"network_forecast": network_input(n, days).model_dump(mode="json")}
    schema, marks, errors = "bench_w3f1_test", {}, {}
    reset_schema(url, schema)
    engine = create_queue_engine(url, schema=schema)
    with engine.begin() as conn:
        command.upgrade(alembic_config(conn), "head")
        conn.execute(sa.text("INSERT INTO organizations (id, name, is_demo) "
                             "VALUES (:o, 'bench', false)"), {"o": ORG})
    registry = Registry([REGISTRATION])
    queue = QueueRepository(engine, registry=registry, profile=PRODUCTION_PROFILE)
    publisher, claimed = REGISTRATION.publisher, queue._lock_claimed

    def timed(name, call):
        def wrapper(*args, **kwargs):
            t = time.perf_counter()
            try:
                return call(*args, **kwargs)
            except Exception as exc:  # the supervisor logs only the type
                errors[name] = f"{type(exc).__name__}: {str(exc)[:300]}"
                raise
            finally:
                marks[name] = time.perf_counter() - t
        return wrapper

    def locked(*args, **kwargs):  # from the lock request: acquiring it counts (verifier N1)
        marks["locked_at"] = time.perf_counter()
        return claimed(*args, **kwargs)

    def publish(*args, **kwargs):  # the queue lock: from calling _lock_claimed to COMMIT
        queue._lock_claimed = locked
        try:
            return timed("queue_publish_s", type(queue).publish.__get__(queue))(*args, **kwargs)
        finally:
            queue._lock_claimed = claimed
            marks["lock_held_s"] = time.perf_counter() - marks.pop("locked_at")

    quiet = {"sleep_s": 0, "spawn_descendant": False, "ignore_sigterm": False, "fail": None}
    try:
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(fake_driver, "_behavior_for", lambda validated, step: quiet)
            patch.setattr(fake_driver, "_with_behavior", lambda validated, step, b: validated)
            patch.setattr(publisher, "prepare", timed("prepare_s", publisher.prepare))
            patch.setattr(publisher, "publish", timed("publisher_publish_s", publisher.publish))
            patch.setattr(queue, "publish", publish)
            supervisor = Supervisor(queue, registry, fake_driver.FakeDriver(registry=registry),
                                    SupervisorConfig(registry_name="bench",
                                                     profile=PRODUCTION_PROFILE, tick_s=0.05))
            assert supervisor.start()
            scope = TrustedScope(ORG, "bench")
            try:
                t = time.perf_counter()
                job_id = queue.submit(scope, "forecast.v1", payload, "bench-lock").job_id
                marks["submit_s"] = time.perf_counter() - t
                while (job := queue.get_job(scope, job_id)).state not in TERMINAL_STATES:
                    supervisor.tick()
                    time.sleep(0.01)
                marks["job_s"] = time.perf_counter() - t
            finally:
                supervisor.shutdown_drain(timeout_s=60)
    finally:
        engine.dispose()
        reset_schema(url, schema)
    attempt = job.attempts[-1]
    return {"series": n, "days": days, "state": job.state.value, "error": attempt.error,
            "errors": errors,
            "timings": {k: round(v, 2) for k, v in marks.items()},
            "input_mb": round(len(json.dumps(payload, separators=(",", ":"))) / 1e6, 2),
            "note": "lock_held_s runs from the call to the queue's _lock_claimed to COMMIT: "
                    "acquiring the lock, its own checks (the job row and the input hash), the "
                    "INSERT, the transitions and COMMIT"}


def freeze(n: int, days: int) -> dict:
    import sqlalchemy as sa

    from app.services.forecasting.network import _history, _history_end

    url = os.environ.get("PP_TEST_DATABASE_URL", "")
    if not url.rsplit("/", 1)[-1].split("?")[0].endswith("_test"):
        raise SystemExit("PP_TEST_DATABASE_URL must name a *_test database")
    engine, schema = sa.create_engine(url), "bench_w3f06_test"
    try:
        with engine.begin() as conn:
            conn.execute(sa.text(f"DROP SCHEMA IF EXISTS {schema} CASCADE; CREATE SCHEMA {schema}"))
            conn.execute(sa.text(
                f"CREATE TABLE {schema}.net_demand_history (dataset_version_id uuid, "
                "location_id uuid, product_id uuid, day date, quantity int, basis text)"))
            conn.execute(sa.text(f"CREATE TABLE {schema}.net_donation_history "
                                 "(dataset_version_id uuid, day date)"))  # empty here
            t = time.perf_counter()
            conn.execute(sa.text(
                f"INSERT INTO {schema}.net_demand_history SELECT :v, "
                "md5('l' || s % 100)::uuid, md5('p' || s / 100)::uuid, "
                "CAST(:cutoff AS date) - d, CASE WHEN random() < 0.05 THEN NULL "
                "ELSE (random() * 60)::int END, 'demand' "
                "FROM generate_series(0, :n - 1) s, generate_series(0, :days - 1) d"),
                {"v": DATASET, "cutoff": CUTOFF, "n": n, "days": days})
            load_s = time.perf_counter() - t
            conn.execute(sa.text(f"ANALYZE {schema}.net_demand_history"))
        with engine.connect() as conn:
            conn.execute(sa.text(f"SET search_path TO {schema}"))
            t = time.perf_counter()
            end = _history_end(conn, DATASET, CUTOFF)
            end_s = time.perf_counter() - t
            t = time.perf_counter()
            rows = _history(conn, "net_demand_history", DATASET, end)
            query_s = time.perf_counter() - t
    finally:
        with engine.begin() as conn:
            conn.execute(sa.text(f"DROP SCHEMA IF EXISTS {schema} CASCADE"))
        engine.dispose()
    return {"series": n, "days": days, "history_rows": n * days, "series_rows": len(rows),
            "scratch_load_s": round(load_s, 2), "history_end_s": round(end_s, 2),
            "history_aggregate_s": round(query_s, 2),
            "note": "one unpartitioned scratch table holding only this version's rows"}


def main() -> None:
    parser = argparse.ArgumentParser(description="Spike S7: forecast and backtest volume")
    parser.add_argument("--part", default="compact",
                        choices=("compact", "existing", "db", "built", "freeze", "lock"))
    parser.add_argument("--series", type=int, default=50_000)
    parser.add_argument("--days", type=int, default=90)
    parser.add_argument("--sample", type=int, default=500)
    args = parser.parse_args()
    load_start, t = os.getloadavg(), time.perf_counter()
    if args.part == "existing":
        result = existing(args.series, args.days, args.sample)
    elif args.part == "db":
        result = db(args.series, args.days)
    elif args.part == "built":
        result = built(args.series, args.days)
    elif args.part == "freeze":
        result = freeze(args.series, args.days)
    elif args.part == "lock":
        result = lock(args.series, args.days)
    else:
        result = compact(args.series, args.days)[0]
    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                            text=True, check=False).stdout.strip()
    result.update(part=args.part, wall_s=round(time.perf_counter() - t, 2),
                  peak_rss_mb=peak_rss_mb(), commit=commit, python=platform.python_version(),
                  cpus=os.cpu_count(), synthetic=True,
                  load_1_5_15={"start": load_start, "end": os.getloadavg()})
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
