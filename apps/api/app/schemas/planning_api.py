"""Explicit planning configuration; operational quantities are loaded on the server."""

from uuid import UUID

from pydantic import Field

from app.schemas.or_inputs import (
    Capacities,
    ORContract,
    Product,
    Reserve,
    Route,
    VulnerabilityAttributes,
)


class CaptureRequest(ORContract):
    forecast_run_id: UUID
    products: tuple[Product, ...] = Field(min_length=1, max_length=2)
    routes: tuple[Route, ...] = Field(max_length=182)
    capacities: Capacities
    reserves: tuple[Reserve, ...] = Field(max_length=28)
    vulnerability_attributes: tuple[VulnerabilityAttributes, ...] = Field(max_length=12)
    expected_source_revision: str | None
