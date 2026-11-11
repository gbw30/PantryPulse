"""Run the first-start sample seed in the connected schema and print the samples (W4-02, V1-A05).

`local_bootstrap.run` (the compose `seed` service) commits the local organization, then calls
`seed_local.seed`, which imports both fictional samples through the W1 importer. The connected
stack starts the API and worker without that service, so this runs the same two steps, dated by
`local_bootstrap.seed_today()`. Like every start, it is idempotent: a sample imported within the
last 7 days is kept. It reads DATABASE_URL and PP_DATABASE_SCHEMA, as db_probe.py does.
Usage: seed_samples.py  (prints {"PANTRY": {"id", "name"}, "RETAIL": {...}} as JSON)
"""

import json
import os
import sys
from pathlib import Path

import sqlalchemy as sa
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "api"))

from app.repositories.jobs import create_queue_engine  # noqa: E402
from app.services.samples import SAMPLES  # noqa: E402
from scripts import seed_local  # noqa: E402
from scripts.local_bootstrap import seed_today  # noqa: E402

if __name__ == "__main__":
    engine = create_queue_engine(
        os.environ["DATABASE_URL"], schema=os.environ["PP_DATABASE_SCHEMA"]
    )
    try:
        with Session(engine) as session, session.begin():
            created = seed_local.ensure_local_organization(session)
        with Session(engine) as session, session.begin():
            print(seed_local.seed(session, seed_today(), created), file=sys.stderr)
        names = [name for name, _ in SAMPLES]
        with engine.connect() as conn:
            rows = conn.execute(sa.text(
                "SELECT DISTINCT ON (n.name) n.id, n.name, n.mode FROM networks n "
                "JOIN dataset_versions v ON v.network_id = n.id "
                "WHERE n.is_sample AND n.name = ANY(:names) "
                "ORDER BY n.name, v.as_of_date DESC, n.id"), {"names": names}).all()
        found = {mode: {"id": str(id_), "name": name} for id_, name, mode in rows}
        if sorted(found) != ["PANTRY", "RETAIL"]:
            raise SystemExit(f"expected one Pantry and one Retail sample, found {sorted(found)}")
        print(json.dumps(found))
    finally:
        engine.dispose()
