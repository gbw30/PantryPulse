"""Explicitly seed fictional history into an EMPTY isolated demo schema; no reset."""

import argparse
import json
import os
import re
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid5

import sqlalchemy as sa

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from app.models import operational as m  # noqa: E402
from scripts.forecasting_fixture import SPEC_PATH, build_fixture  # noqa: E402


def seed_history(conn, *, first_planning_date=None):
    """One transaction: catalog + revisions only. No inventory, supply or fake forecast."""
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    if first_planning_date is not None:
        start = first_planning_date - timedelta(days=spec["history_days"])
        spec["start_date"] = start.isoformat()
    history, policy, _origins, as_of = build_fixture(spec)
    org, dataset = history.organization_id, history.dataset_id
    if conn.scalar(sa.select(sa.func.count()).select_from(m.Organization)):
        raise ValueError("Demo loader requires an empty schema; existing data is never reset")
    known = datetime(2026, 7, 1, tzinfo=UTC)
    own = dict(organization_id=org)

    def insert(model, rows):
        if rows:
            conn.execute(sa.insert(model), [dict(recorded_at=known, **row) for row in rows])

    insert(m.Organization, [dict(id=org, name="PantryPulse fictional forecast demo", is_demo=True)])
    insert(
        m.DataSource,
        [dict(**own, id=dataset, name="Fictional 90-day history", classification="SIMULATED")],
    )
    sites, calendars, products = [], [], []
    calendar_ids = {}
    for s in spec["sites"]:
        sid = uuid5(dataset, s["name"])
        cid = uuid5(sid, "calendar-v1")
        calendar_ids[sid] = cid
        sites.append(dict(**own, id=sid, name=s["name"], role=s["role"], active=True))
        calendars.append(dict(**own, id=cid, site_id=sid, revision=1, timezone=spec["timezone"]))
    insert(m.Site, sites)
    insert(m.SiteCalendar, calendars)
    for sid, cid in calendar_ids.items():
        conn.execute(sa.update(m.Site).where(m.Site.id == sid).values(current_calendar_id=cid))
    categories = []
    for p in spec["products"]:
        pid = uuid5(dataset, p["name"])
        cat = uuid5(pid, "category")
        categories.append(dict(**own, id=cat, name=p["name"], active=True))
        products.append(
            dict(**own, id=pid, category_id=cat, name=p["name"], base_unit=p["unit"], active=True)
        )
    insert(m.Category, categories)
    insert(m.Product, products)
    records, revisions = {}, []
    for r in history.demand:
        rid = uuid5(dataset, r.source.logical_key)
        records[rid] = dict(
            **own,
            id=rid,
            site_id=r.key.site_id,
            product_id=r.key.product_id,
            local_day=r.day,
            source_id=dataset,
            source_record_key=r.source.logical_key,
        )
        revisions.append(
            dict(
                **own,
                id=r.source.revision_id,
                record_id=rid,
                site_id=r.key.site_id,
                calendar_version_id=calendar_ids[r.key.site_id],
                revision=r.source.revision,
                requested=None if r.requested_units is None else int(r.requested_units),
                fulfilled=None if r.fulfilled_units is None else int(r.fulfilled_units),
                unmet=None if r.unmet_units is None else int(r.unmet_units),
                recorded_at=r.source.recorded_at,
            )
        )
    insert(m.DemandRecord, list(records.values()))
    conn.execute(sa.insert(m.DemandRevision), revisions)
    insert(
        m.Donor,
        [
            dict(**own, id=did, name="Fictional donor", active=True)
            for did in sorted({r.donor_id for r in history.receipts}, key=str)
        ],
    )
    receipts, headers, lines = {}, [], []
    for r in history.receipts:
        rid = uuid5(dataset, r.source.logical_key)
        receipts[rid] = dict(
            **own, id=rid, source_id=dataset, source_record_key=r.source.logical_key
        )
        headers.append(
            dict(
                **own,
                id=r.source.revision_id,
                receipt_id=rid,
                receiving_site_id=r.receiving_site_id,
                donor_id=r.donor_id,
                calendar_version_id=calendar_ids[r.receiving_site_id],
                revision=r.source.revision,
                received_at=r.received_at,
                local_day=r.local_day,
                is_void=r.is_void,
                recorded_at=r.source.recorded_at,
            )
        )
        lines.extend(
            dict(
                **own,
                id=uuid5(r.source.revision_id, str(line.line_id)),
                receipt_revision_id=r.source.revision_id,
                line_key=str(line.line_id),
                product_id=line.product_id,
                received_quantity=int(line.received_units),
                recorded_at=r.source.recorded_at,
            )
            for line in r.lines
        )
    insert(m.Receipt, list(receipts.values()))
    conn.execute(sa.insert(m.ReceiptRevision), headers)
    conn.execute(sa.insert(m.ReceiptLine), lines)
    conn.execute(
        sa.insert(m.DonationCoverageRevision),
        [
            dict(
                **own,
                id=r.source.revision_id,
                site_id=r.key.site_id,
                product_id=r.key.product_id,
                source_id=dataset,
                calendar_version_id=calendar_ids[r.key.site_id],
                local_day=r.day,
                revision=r.source.revision,
                complete=r.complete,
                recorded_at=r.source.recorded_at,
            )
            for r in history.coverage
        ],
    )
    cutoff = max(r.day for r in history.demand)
    return dict(
        organization_id=str(org),
        request=dict(
            source_id=str(dataset),
            data_cutoff_date=cutoff.isoformat(),
            history_start_date=spec["start_date"],
            snapshot_as_of=as_of.isoformat(),
            policy=policy.model_dump(mode="json"),
            force_refresh=False,
        ),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", required=True)
    output = parser.add_mutually_exclusive_group(required=True)
    output.add_argument("--request-file", type=Path)
    output.add_argument("--stdout", action="store_true", help="emit request JSON after commit")
    args = parser.parse_args()
    if not re.fullmatch(r"pp45_demo_[a-z0-9_]{1,40}", args.schema):
        parser.error("Use a dedicated pp45_demo_* schema, never public")
    url = os.environ.get("DATABASE_URL_UNPOOLED")
    if not url:
        parser.error("An explicit direct DATABASE_URL_UNPOOLED is required")
    from alembic import command
    from alembic.config import Config

    from app.database import database_engine

    engine = database_engine(url)
    try:
        with engine.begin() as conn:
            conn.execute(sa.schema.CreateSchema(args.schema))
            config = Config(str(API_ROOT / "alembic.ini"))
            config.attributes.update(connection=conn, schema=args.schema)
            command.upgrade(config, "head")
            conn.execute(sa.text(f'SET LOCAL search_path TO "{args.schema}"'))
            result = seed_history(conn)
            if args.request_file:
                # A file-output failure must roll back the NEW schema and its data too.
                args.request_file.write_text(json.dumps(result, indent=2), encoding="utf-8")
        if args.stdout:
            print(json.dumps(result, indent=2))
        else:
            print(f"Seeded fictional history in {args.schema}; "
                  "request written to the selected file.")
    except Exception as error:
        print(
            f"Demo setup failed ({type(error).__name__}); no existing data reset.", file=sys.stderr
        )
        return 1
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
