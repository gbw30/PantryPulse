"""Fictional sample networks, loaded by the local seed on every start (W3-P04).

Each sample goes through the W1 importer (`create_import` + `run_import`), never straight into
the tables. An absent sample is imported; one whose newest version is more than 7 days old gets
a freshly dated version (a re-import into the same network, V1-SPEC §8). Nothing is reset or
removed, and nothing calls out: samples carry coordinates and sample rates, and `run_import`
queues no enrichment.
"""

import hashlib
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import sqlalchemy as sa

from app.repositories import imports as repo
from app.schemas.v1_imports import ImportCreate, NewNetwork
from app.services.imports import api, staging
from app.services.samples import pantry, retail
from app.services.samples.network import SampleNetwork

FRESH_DAYS = 7
SAMPLES = ((pantry.NAME, pantry.pantry_sample), (retail.NAME, retail.retail_sample))


@dataclass(frozen=True)
class SeedReport:
    loaded: tuple[str, ...] = ()


def ensure_samples(session, today: date) -> SeedReport:
    """`session` is the seed's ORM session; each import commits on its own connections, as the
    import job does (the seed runs before the worker starts, so the API commit path can't).

    It commits the session's pending work (the bootstrap's login and organization inserts)
    first: publishing an import attaches a `net_batches` partition, whose foreign key needs
    SHARE ROW EXCLUSIVE on `organizations`, and the caller's open insert would block it forever
    (a client-side deadlock PostgreSQL can't detect)."""
    session.commit()
    engine = session.get_bind()
    loaded = []
    for name, build in SAMPLES:
        with engine.connect() as conn:
            found = conn.execute(sa.text(
                "SELECT n.id, max(v.as_of_date) FROM networks n "
                "JOIN dataset_versions v ON v.network_id = n.id "
                "WHERE n.is_sample AND n.name = :name GROUP BY n.id "
                # Names aren't unique (two seeds racing): the freshest network decides.
                "ORDER BY max(v.as_of_date) DESC, n.id LIMIT 1"),
                {"name": name}).one_or_none()
        if found is not None and (today - found[1]).days <= FRESH_DAYS:
            continue
        _import(engine, build(today), None if found is None else found[0])
        loaded.append(name)
    return SeedReport(loaded=tuple(loaded))


def _import(engine: sa.Engine, sample: SampleNetwork, network_id: UUID | None) -> None:
    request = ImportCreate(network_id=network_id) if network_id else ImportCreate(
        network=NewNetwork(name=sample.name, mode=sample.mode, timezone=sample.timezone))
    import_id = api.create_import(SimpleNamespace(engine=engine), None, request,
                                  is_sample=True).import_id
    with tempfile.TemporaryDirectory(prefix="pp-samples-") as folder:
        base = Path(folder)
        with engine.begin() as conn:
            for name, text in sample.files.items():
                data = text.encode()
                path = staging.upload_path(base, import_id, name)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                repo.record_file(conn, import_id, name, len(data), hashlib.sha256(data).hexdigest())
        outcome = staging.run_import(engine, import_id, sample.as_of_date, base, actor="seed")
    if not outcome.ok:  # our own generated files: a failure is a bug, so the seed stops loudly
        raise RuntimeError(f"sample {sample.name!r} did not import: {outcome.errors[:3]}")
