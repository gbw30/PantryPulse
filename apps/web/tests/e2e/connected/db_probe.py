"""Read-only probe for the connected e2e specs: per table, "<md5 of every row>:<row count>".

It reads DATABASE_URL and PP_DATABASE_SCHEMA, the variables the connected API and worker use (the CI
connected step sets both; so does the lane's launcher). A changed value in any row changes the
digest, so "unchanged" means every row, not just the count (W2-05 journey's snapshot).
With --dataset, a table that has a dataset_version_id column is read for that version only, so an
import by a spec running in parallel can't change the digest; every other table is read whole.
With --since TS --name NAME, every table is read whole except rows of networks and dataset versions
recorded since TS whose network is not named NAME: parallel specs' imports are left out, while
anything saved for NAME, or any row with no network, still counts. --clock prints the database time.
Usage: db_probe.py [--dataset UUID | --since TS --name NAME] TABLE [TABLE ...] | db_probe.py --clock
"""

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / "api"))

import uuid  # noqa: E402

import sqlalchemy as sa  # noqa: E402
from app.database import database_engine  # noqa: E402

NAME = re.compile(r"[a-z][a-z0-9_]{0,62}")
schema, tables = os.environ["PP_DATABASE_SCHEMA"], sys.argv[1:]
dataset = since = name = None
if tables[:1] == ["--dataset"]:
    dataset, tables = str(uuid.UUID(tables[1])), tables[2:]
elif tables[:1] == ["--since"] and tables[2:3] == ["--name"]:
    since, name, tables = tables[1], tables[3], tables[4:]
clock = tables == ["--clock"]
if clock:
    tables = ["networks"]  # only to pass the check below; --clock reads no table
if not tables or not NAME.fullmatch(schema) or not all(NAME.fullmatch(t) for t in tables):
    raise SystemExit("usage: db_probe.py [--dataset UUID] TABLE [TABLE ...] (plain identifiers only)")


# Rows of other specs' new networks and dataset versions (recorded since `since`, network not `name`).
OTHERS_VERSION = ("EXISTS (SELECT 1 FROM dataset_versions v JOIN networks n ON n.id = v.network_id"
                  " WHERE v.id = {col} AND v.recorded_at >= :since AND n.name <> :name)")
OTHERS = {
    "networks": "r.recorded_at >= :since AND r.name <> :name",
    "dataset_versions": OTHERS_VERSION.format(col="r.id"),
}


def has_column(conn, table: str, column: str) -> bool:
    return conn.scalar(sa.text(
        "SELECT count(*) FROM information_schema.columns WHERE table_schema = :s"
        " AND table_name = :t AND column_name = :c"), {"s": schema, "t": table, "c": column}) == 1


def where(conn, table: str) -> str:
    if since is not None:
        others = OTHERS.get(table) or (OTHERS_VERSION.format(col="r.dataset_version_id")
                                       if has_column(conn, table, "dataset_version_id") else None)
        return f" WHERE NOT ({others})" if others else ""
    scoped = dataset is not None and has_column(conn, table, "dataset_version_id")
    return " WHERE r.dataset_version_id = :d" if scoped else ""


engine = database_engine(os.environ["DATABASE_URL"])
try:
    with engine.connect() as conn:
        conn.execute(sa.text(f'SET search_path TO "{schema}"'))
        if clock:
            print(json.dumps({"now": conn.scalar(sa.text("SELECT now()::text"))}))
            raise SystemExit(0)
        print(
            json.dumps(
                {
                    t: conn.scalar(
                        sa.text(
                            "SELECT md5(coalesce(string_agg(r::text, '|' ORDER BY r::text), ''))"
                            f" || ':' || count(*) FROM {t} r"
                            + where(conn, t)
                        ),
                        {"d": dataset, "since": since, "name": name},
                    )
                    for t in tables
                }
            )
        )
finally:
    engine.dispose()
