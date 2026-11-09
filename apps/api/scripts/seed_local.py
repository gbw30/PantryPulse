"""Seed the local install idempotently; called by local_bootstrap.py on every start.

Never resets or deletes: it only adds what is missing.
"""

from datetime import date
from uuid import UUID

import sqlalchemy as sa

from app.services import samples

# Fixed so every start finds the same row instead of adding one. compose.yaml passes the same
# value as PP_PRESENTER_ORGANIZATION_ID.
LOCAL_ORGANIZATION_ID = UUID("6f0c5a52-4c2e-5d1b-9a57-0b1f4c7d2e01")


def ensure_local_organization(session) -> bool:
    """Insert the local install organization once; return True only when it was created."""
    created = session.execute(
        sa.text(
            "INSERT INTO organizations (id, name, is_demo) VALUES (:id, :name, false) "
            "ON CONFLICT (id) DO NOTHING"
        ),
        {"id": LOCAL_ORGANIZATION_ID, "name": "Local install"},
    ).rowcount
    return created == 1


def seed(session, today: date, organization_created: bool) -> str:
    """Add the sample networks; return a summary line. The bootstrap has already committed the
    local organization, so this transaction writes nothing that an import's attach waits on."""
    report = samples.ensure_samples(session, today)
    state = "created" if organization_created else "already present"
    return f"Seed completed: local organization {state}; samples loaded: {len(report.loaded)}."
