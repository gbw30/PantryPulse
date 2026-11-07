"""v1 allocation methods on one or-input-v3 scenario (W1-S02/S03).

W0-08 stub: frozen signatures; the owning lane task replaces each body."""

from app.schemas.v1_planning import AllocationMethod, Measure, MethodResult, ORInputV3
from app.services.v1_errors import NotImplementedV1


def run_method(scenario: ORInputV3, method: AllocationMethod, measure: Measure) -> MethodResult:
    raise NotImplementedV1("W1-S02")
