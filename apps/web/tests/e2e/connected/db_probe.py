"""Read-only probe for the connected e2e specs: per table, "<md5 of every row>:<row count>".

It reads DATABASE_URL and PP_DATABASE_SCHEMA, the variables the connected API and worker use (the CI
connected step sets both; so does the lane's launcher). A changed value in any row changes the
digest, so "unchanged" means every row, not just the count (W2-05 journey's snapshot).
Usage: db_probe.py TABLE [TABLE ...]
"""

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "api"))

import sqlalchemy as sa  # noqa: E402
from app.database import database_engine  # noqa: E402

NAME = re.compile(r"[a-z][a-z0-9_]{0,62}")
schema, tables = os.environ["PP_DATABASE_SCHEMA"], sys.argv[1:]
if not tables or not NAME.fullmatch(schema) or not all(NAME.fullmatch(t) for t in tables):
    raise SystemExit("usage: db_probe.py TABLE [TABLE ...] (plain identifiers only)")
engine = database_engine(os.environ["DATABASE_URL"])
try:
    with engine.connect() as conn:
        conn.execute(sa.text(f'SET search_path TO "{schema}"'))
        print(
            json.dumps(
                {
                    t: conn.scalar(
                        sa.text(
                            "SELECT md5(coalesce(string_agg(r::text, '|' ORDER BY r::text), ''))"
                            f" || ':' || count(*) FROM {t} r"
                        )
                    )
                    for t in tables
                }
            )
        )
finally:
    engine.dispose()
