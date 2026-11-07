"""Time the import.v1 job on a generated network (W1-D05): the DB-less `validate` step, `prepare`
(outside the queue lock) and `publish` (inside it), plus the process's peak RSS.

    uv run --frozen python scripts/bench_import.py --rows 4500000

Writes artifacts/bench/import.json. Uses PP_TEST_DATABASE_URL (a *_test database only) and its
own schema, dropped afterwards. Everything runs in this one process, so peak RSS covers the step,
which runs in a contained child under the real supervisor.
"""

import argparse
import hashlib
import json
import os
import platform
import resource
import sys
import tempfile
import time
import uuid
from datetime import date, timedelta
from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from app.repositories import imports as repo  # noqa: E402
from app.repositories.jobs import create_queue_engine  # noqa: E402
from app.schemas.v1_imports import NewNetwork  # noqa: E402
from app.services.imports.staging import (  # noqa: E402
    job_input,
    load_staged,
    publish_staged,
    upload_path,
    write_load_files,
)

AS_OF = date(2026, 11, 4)
LOCATIONS, PRODUCTS, DAYS = 100, 500, 90  # the v1 envelope: 4.5 M demand rows at most
HEADERS = {
    "locations": "location_id,name,type,street,city,state,zip,latitude,longitude",
    "products": "product_id,name,unit",
    "inventory": "location_id,product_id,batch_id,quantity,expiry_date,non_expiring,"
                 "received_date",
    "demand_history": "location_id,product_id,date,quantity,basis",
}


def _rows(name: str, rows: int, batches: int):
    if name == "locations":
        for i in range(LOCATIONS):
            yield (f"L{i:03},Site {i},{'hub' if i < 5 else 'pantry'},{i + 1} Main St,"
                   f"Tallahassee,FL,32301,{27 + i % 10 * 0.3:.4f},{-82 - i // 10 * 0.3:.4f}")
    elif name == "products":
        yield from (f"P{p:03},Product {p},case" for p in range(PRODUCTS))
    elif name == "inventory":
        expiry = AS_OF + timedelta(days=30)
        yield from (f"L{b % LOCATIONS:03},P{b // LOCATIONS % PRODUCTS:03},B{b},10,{expiry},,"
                    for b in range(batches))
    else:
        days = [AS_OF - timedelta(days=d) for d in range(DAYS, 0, -1)]
        pairs = ((i, p) for i in range(LOCATIONS) for p in range(PRODUCTS))
        cells = ((i, p, day) for i, p in pairs for day in days)
        for _, (i, p, day) in zip(range(rows), cells, strict=False):
            yield f"L{i:03},P{p:03},{day},{(i + p + day.day) % 7},demand"


def generate(base: Path, run_id: uuid.UUID, rows: int, batches: int) -> dict[str, tuple]:
    """Write the four required files; name -> (bytes, sha256)."""
    files = {}
    for name, header in HEADERS.items():
        path = upload_path(base, run_id, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256()
        with path.open("wb") as out:
            for line in (header, *_rows(name, rows, batches)):
                data = f"{line}\n".encode()
                out.write(data)
                digest.update(data)
        files[name] = (path.stat().st_size, digest.hexdigest())
    return files


def _reset(url: str, schema: str, *, create: bool) -> None:
    raw = sa.create_engine(url)
    with raw.begin() as conn:
        name = conn.scalar(sa.text("SELECT current_database()"))
        if not name.endswith("_test"):
            raise SystemExit(f"refusing to touch non-test database {name!r}")
        conn.execute(sa.text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        if create:
            conn.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    raw.dispose()


def main(argv=None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rows", type=int, default=LOCATIONS * PRODUCTS * DAYS,
                        help="demand_history rows (at most 4,500,000)")
    parser.add_argument("--batches", type=int, default=200_000, help="inventory rows")
    parser.add_argument("--schema", default="w1_data_bench")
    parser.add_argument("--out", type=Path,
                        default=API_ROOT.parents[1] / "artifacts" / "bench" / "import.json")
    args = parser.parse_args(argv)
    if not 0 < args.rows <= LOCATIONS * PRODUCTS * DAYS or not 0 < args.batches <= 200_000:
        parser.error("--rows must be 1..4,500,000 and --batches 1..200,000 (the v1 envelope)")
    url = os.environ.get("PP_TEST_DATABASE_URL") or parser.error("set PP_TEST_DATABASE_URL")
    _reset(url, args.schema, create=True)
    engine = create_queue_engine(url, schema=args.schema)
    seconds, clock = {}, [time.perf_counter()]

    def lap(name):
        now = time.perf_counter()
        seconds[name] = round(now - clock[0], 4)
        clock[0] = now

    try:
        with engine.begin() as conn:
            cfg = Config(str(API_ROOT / "alembic.ini"))
            cfg.set_main_option("script_location", str(API_ROOT / "migrations"))
            cfg.attributes["connection"] = conn
            command.upgrade(cfg, "head")
            run = repo.create_run(conn, NewNetwork(name="Bench", mode="PANTRY",
                                                   timezone="America/New_York"), None)
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            clock[0] = time.perf_counter()
            files = generate(base, run.id, args.rows, args.batches)
            with engine.begin() as conn:
                for name, (size, sha) in files.items():
                    repo.record_file(conn, run.id, name, size, sha)
                job = job_input(conn, repo.get_run(conn, run.id), AS_OF, base, "bench")
            lap("generate")
            attempt = uuid.uuid4()
            step = write_load_files(job, attempt)
            lap("step")
            if not step["ok"]:
                raise SystemExit(f"generated files did not validate: {step['errors'][:3]}")
            load_staged(engine, attempt, job, step)
            lap("prepare")
            with engine.begin() as conn:
                publish_staged(conn, run.organization_id, attempt, job, step)
            lap("publish")
        seconds["total"] = round(seconds["step"] + seconds["prepare"] + seconds["publish"], 4)
        with engine.connect() as conn:
            loaded = {table: conn.scalar(sa.text(
                f"SELECT count(*) FROM {table} WHERE dataset_version_id = :v"),
                {"v": step["dataset_version_id"]}) for table in ("net_batches",
                                                                 "net_demand_history")}
    finally:
        engine.dispose()
        _reset(url, args.schema, create=False)
    report = {
        "generated": {"locations": LOCATIONS, "products": PRODUCTS, "batches": args.batches,
                      "demand_history": args.rows},
        "loaded": loaded,
        "seconds": seconds,  # total = step + prepare + publish; publish holds the queue lock
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        "host": {"platform": platform.platform(), "python": platform.python_version(),
                 "cpus": os.cpu_count()},
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))
    return report


if __name__ == "__main__":
    main()
