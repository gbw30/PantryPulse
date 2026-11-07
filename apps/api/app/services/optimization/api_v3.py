"""Router-facing v1 comparisons: submit or-comparison.v3, read, actions, export (W1-S04/S06/S07).

W0-08 stub: frozen signatures; the owning lane task replaces each body."""

from collections.abc import Sequence
from uuid import UUID

from app.schemas.forecast_api import ForecastAccepted
from app.schemas.v1_planning import (
    AllocationMethod,
    ComparisonRequestV3,
    DecisionActions,
    SavedComparisonV3,
)
from app.services.v1_errors import NotImplementedV1


def submit_comparison(
    rt, scope, network_id: UUID, request: ComparisonRequestV3, idempotency_key: str
) -> ForecastAccepted:
    """Checks the methods against the scenario's mode with require_methods_for_mode (422)."""
    raise NotImplementedV1("W1-S04")


def get_comparison(rt, scope, network_id: UUID, comparison_id: UUID) -> SavedComparisonV3:
    raise NotImplementedV1("W1-S04")


def comparison_actions(
    rt, scope, network_id: UUID, comparison_id: UUID, method: AllocationMethod
) -> DecisionActions:
    raise NotImplementedV1("W1-S06")


def export_comparison(
    rt,
    scope,
    network_id: UUID,
    comparison_id: UUID,
    method: AllocationMethod,
    action_ids: Sequence[str],
) -> str:
    raise NotImplementedV1("W1-S07")
