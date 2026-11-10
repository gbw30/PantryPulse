"""Seed a SAMPLE network from a fixture set, as the internal sample seed does (CR-w3-samples-1).

No route marks a network as a sample (`create_import`'s `is_sample` is for the internal seed only),
and the seeded samples arrive in W4. Until then this runs the same importer the API runs
(`repo.create_run(..., is_sample=True)`, the API's upload writer, then `run_import`) in the
connected schema, so the browser can check how a sample's pre-filled rates are labeled. It
reads DATABASE_URL and PP_DATABASE_SCHEMA, as db_probe.py does.
Usage: seed_sample.py NAME PANTRY|RETAIL SET_DIR  (prints the network_id)
"""

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "api"))

from app.repositories import imports as repo  # noqa: E402
from app.repositories.jobs import create_queue_engine  # noqa: E402
from app.schemas.v1_imports import NewNetwork  # noqa: E402
from app.services.imports.staging import run_import  # noqa: E402
from tests.imports.test_import_postgres import _write  # noqa: E402

if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("usage: seed_sample.py NAME PANTRY|RETAIL SET_DIR")
    name, mode, folder = sys.argv[1], sys.argv[2], Path(sys.argv[3])
    files = {p.stem: p.read_text() for p in sorted(folder.glob("*.csv"))}
    engine = create_queue_engine(
        os.environ["DATABASE_URL"], schema=os.environ["PP_DATABASE_SCHEMA"]
    )
    try:
        with engine.begin() as conn:
            run = repo.create_run(
                conn,
                NewNetwork(name=name, mode=mode, timezone="America/New_York"),
                None,
                is_sample=True,
            )
        with tempfile.TemporaryDirectory() as base:
            _write(engine, Path(base), run.id, files)
            outcome = run_import(engine, run.id, None, Path(base), actor="e2e-sample-seed")
        if not outcome.ok:
            raise SystemExit(f"the sample import failed: {outcome.errors[:3]}")
        print(outcome.network_id)
    finally:
        engine.dispose()
