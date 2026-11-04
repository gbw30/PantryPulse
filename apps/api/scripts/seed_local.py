"""Seed the local install idempotently: run by the compose `seed` service on every start.

Never resets or deletes. W0-05 adds the generated login and the sample networks here.
"""

import os
import sys
from pathlib import Path
from uuid import UUID

import sqlalchemy as sa

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from app.database import database_engine  # noqa: E402

# Fixed so every start finds the same row instead of adding one.
LOCAL_ORGANIZATION_ID = UUID("6f0c5a52-4c2e-5d1b-9a57-0b1f4c7d2e01")


def ensure_local_organization(conn) -> bool:
    """Insert the local install organization once; return True only when it was created."""
    created = conn.execute(
        sa.text(
            "INSERT INTO organizations (id, name, is_demo) VALUES (:id, :name, false) "
            "ON CONFLICT (id) DO NOTHING"
        ),
        {"id": LOCAL_ORGANIZATION_ID, "name": "Local install"},
    ).rowcount
    return created == 1


def main() -> int:
    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL is required.", file=sys.stderr)
        return 1
    engine = database_engine(url)
    try:
        with engine.begin() as conn:
            created = ensure_local_organization(conn)
        state = "created" if created else "already present"
        print(f"Seed completed: local organization {state}.")
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
