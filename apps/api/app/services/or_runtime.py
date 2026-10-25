"""Lazy database/queue wiring. Importing API/OpenAPI never starts a worker or model."""

import os
from dataclasses import dataclass
from uuid import UUID

import sqlalchemy as sa

from app.repositories.jobs import QueueRepository, create_queue_engine
from app.services.jobs.contracts import RuntimeProfile
from app.workers.registries import load_registry


@dataclass
class ORRuntime:
    engine: sa.Engine
    queue: QueueRepository
    public_organization_id: UUID | None

    @classmethod
    def from_environment(cls) -> "ORRuntime | None":
        url = os.environ.get("DATABASE_URL")
        if not url:
            return None
        engine = create_queue_engine(url, schema=os.environ.get("PP_OR_SCHEMA"))
        public_org = os.environ.get("PP_PRESENTER_ORGANIZATION_ID")
        return cls(
            engine,
            QueueRepository(engine, registry=load_registry("production"), profile=RuntimeProfile()),
            UUID(public_org) if public_org else None,
        )
