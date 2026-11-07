"""Bring-your-own Google key: lookup preview and cached fetch (W1-D08).

W0-08 stub: frozen signatures; the owning lane task replaces each body."""

from uuid import UUID

from app.schemas.forecast_api import ForecastAccepted
from app.schemas.v1_enrichment import GoogleLookupPreview
from app.services.v1_errors import NotImplementedV1


def preview_lookups(rt, scope, network_id: UUID) -> GoogleLookupPreview:
    raise NotImplementedV1("W1-D08")


def fetch_routes(rt, scope, network_id: UUID, idempotency_key: str) -> ForecastAccepted:
    raise NotImplementedV1("W1-D08")
