"""Plan export CSV; simulated, changes no stock (W1-S07).

W0-08 stub: frozen signatures; the owning lane task replaces each body."""

from collections.abc import Sequence

from app.schemas.v1_planning import AllocationMethod, SavedComparisonV3
from app.services.v1_errors import NotImplementedV1


def export_plan_csv(
    comparison: SavedComparisonV3, method: AllocationMethod, action_ids: Sequence[str]
) -> str:
    raise NotImplementedV1("W1-S07")
