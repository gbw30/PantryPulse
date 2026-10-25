"""Create a NEW isolated fictional planning schema, with audited stock. Never reset."""

import argparse
import json
import os
import re
import sys
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4, uuid5
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from sqlalchemy.orm import Session

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from app.models import operational as m  # noqa: E402
from app.models.optimization import PlanningAssumptions  # noqa: E402
from app.repositories.operational import append_receipt_revision  # noqa: E402
from app.schemas.operational import ReceiptRevision  # noqa: E402
from app.schemas.optimization_api import AssumptionsPayload  # noqa: E402
from app.schemas.stock import PostReceipt, StockActor  # noqa: E402
from app.services.inventory.stock import execute_stock  # noqa: E402
from app.services.optimization.canonical import operational_hash  # noqa: E402
from scripts.load_forecast_demo import seed_history  # noqa: E402


def seed_demo(conn):
    now = conn.scalar(sa.text("SELECT clock_timestamp()"))
    today = now.astimezone(ZoneInfo("America/New_York")).date()
    demo = seed_history(conn, first_planning_date=today)
    org, source = UUID(demo["organization_id"]), UUID(demo["request"]["source_id"])
    with Session(bind=conn, join_transaction_mode="create_savepoint") as session:
        sites = list(
            session.scalars(
                sa.select(m.Site).where(m.Site.organization_id == org).order_by(m.Site.id)
            )
        )
        products = list(
            session.scalars(
                sa.select(m.Product).where(m.Product.organization_id == org).order_by(m.Product.id)
            )
        )
        donor = session.scalar(sa.select(m.Donor).where(m.Donor.organization_id == org).limit(1))
        for index, site in enumerate(sites):
            key = f"simulated-opening-stock:{site.id}"
            receipt = m.Receipt(
                id=uuid4(), organization_id=org, source_id=source, source_record_key=key
            )
            session.add(receipt)
            session.flush()
            revision = append_receipt_revision(
                session,
                ReceiptRevision(
                    organization_id=org,
                    receipt_id=receipt.id,
                    revision_id=uuid4(),
                    revision=1,
                    source_id=source,
                    source_record_key=key,
                    source_classification="SIMULATED",
                    receiving_site_id=site.id,
                    donor_id=donor.id,
                    calendar_version_id=site.current_calendar_id,
                    received_at=now,
                    local_day=today,
                    timezone="America/New_York",
                    recorded_at=now,
                    is_void=False,
                    lines=tuple(
                        dict(
                            line_key=str(p.id),
                            product_id=p.id,
                            quantity=120 if site.role == "HUB" else 70 if index == 0 else 5,
                        )
                        for p in products
                    ),
                ),
            )
            execute_stock(
                session,
                StockActor(organization_id=org, actor="isolated-demo-seeder"),
                PostReceipt(
                    idempotency_key=key,
                    reason="Fictional isolated demo opening stock",
                    revision_id=revision.id,
                    expected_versions=tuple(
                        dict(site_id=site.id, product_id=p.id, version=1) for p in products
                    ),
                    declarations=tuple(
                        dict(
                            line_key=str(p.id),
                            eligibility="ELIGIBLE",
                            expiry=dict(
                                kind="DATED" if i == 0 else "NON_EXPIRING",
                                expires_on=today + timedelta(days=4) if i == 0 else None,
                            ),
                        )
                        for i, p in enumerate(products)
                    ),
                    supply_matches=(),
                    supply_versions=(),
                ),
            )
        session.commit()
        fixture = json.loads(
            (API_ROOT.parents[1] / "data/demo/or-v2/six-beneficiary-v2.snapshot.json").read_text()
        )
        def cap(n):
            return dict(original=n, fixed_used=0, residual=n, source_revision="simulated-preset-v1")
        policy = fixture["policy"]
        payload = AssumptionsPayload(
            policy=policy,
            handling=[dict(product_id=p.id, coefficient=1) for p in products],
            routes=[
                dict(
                    id=uuid5(source, f"route:{a.id}:{b.id}"),
                    source_id=a.id,
                    destination_id=b.id,
                    enabled=True,
                    eta_days=0,
                    capacity=cap(120),
                    costs=[dict(product_id=p.id, cost_minor=1) for p in products],
                    cost_unit="SIMULATED_COST_POINT",
                )
                for a in sites
                for b in sites
                if a.id != b.id and b.role == "BENEFICIARY"
            ],
            capacities=dict(
                global_handling=cap(240),
                cost_budget_minor=240,
                sites=[
                    dict(
                        site_id=s.id,
                        source=cap(240),
                        receiving=[cap(240)] * 7,
                        storage=[cap(1000)] * 7,
                    )
                    for s in sites
                ],
            ),
            reserves=[
                dict(site_id=s.id, product_id=p.id, floors=[0] * 7) for s in sites for p in products
            ],
            vulnerability_attributes=[
                dict(
                    site_id=s.id,
                    scores=[
                        dict(
                            attribute_id=c["attribute_id"],
                            score_bp=min(10000, 1000 + index * 1200),
                            raw_note="Fictional demo score",
                            transformation="Direct simulated basis-point score",
                            transformation_version="sim-v1",
                            classification="SIMULATED",
                        )
                        for c in policy["coefficients"]
                    ],
                )
                for index, s in enumerate(sites)
                if s.role == "BENEFICIARY"
            ],
        )
    identity = uuid4()
    conn.execute(
        sa.insert(PlanningAssumptions).values(
            id=identity,
            organization_id=org,
            name="Editable simulated research preset",
            parent_id=None,
            payload=payload.model_dump(mode="json"),
            content_hash=operational_hash(payload),
            actor="isolated-demo-seeder",
        )
    )
    # History is deliberately fictional; snapshot time is the committed seeding boundary.
    demo["request"]["snapshot_as_of"] = now.isoformat()
    return {**demo, "assumptions_id": str(identity), "classification": "SIMULATED"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r"ppor_demo_[a-z0-9_]{1,40}", args.schema):
        parser.error("Use a NEW dedicated ppor_demo_* schema")
    url = os.environ.get("DATABASE_URL_UNPOOLED")
    if not url:
        parser.error("Explicit direct DATABASE_URL_UNPOOLED is required")
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
            result = seed_demo(conn)
            args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"Created isolated simulated demo in {args.schema}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
