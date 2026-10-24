"""Mode-dependent route eligibility predicate (BACKEND-SPEC.md section 13.2, BE-02).

Topology permission only. MODE_ROUTE_ALLOWED is not permission to dispatch, proof of
donor surplus, or completed shipment validation; dated donor/lot/route/capacity checks
remain OPEN-21/22. Pure and deterministic: no database, network, filesystem or solver use.
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from app.schemas.planning_primitives import TransferMode


class SiteRole(StrEnum):
    """Internal role vocabulary for this helper, not a finalized site schema."""

    HUB = "HUB"
    BENEFICIARY = "BENEFICIARY"


class RouteDecisionReason(StrEnum):
    SELF_TRANSFER = "SELF_TRANSFER"
    ROUTE_DISABLED = "ROUTE_DISABLED"
    DESTINATION_NOT_BENEFICIARY = "DESTINATION_NOT_BENEFICIARY"
    ORIGIN_NOT_ALLOWED_BY_MODE = "ORIGIN_NOT_ALLOWED_BY_MODE"
    MODE_ROUTE_ALLOWED = "MODE_ROUTE_ALLOWED"


@dataclass(frozen=True, slots=True)
class ModeRouteDecision:
    allowed: bool
    reason: RouteDecisionReason


def _as_enum[E: StrEnum](value: object, enum_type: type[E], name: str) -> E:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a str or {enum_type.__name__}, got {type(value).__name__}")
    if isinstance(value, enum_type):
        return value
    # Exact value match only: no trimming or case folding. Members of another str enum
    # are compared by their raw string value and rejected unless it is an exact match.
    raw = str.__str__(value)
    for member in enum_type:
        if member.value == raw:
            return member
    raise ValueError(f"{name} must be one of {[m.value for m in enum_type]}, got {raw!r}")


def _require_uuid(value: object, name: str) -> UUID:
    if not isinstance(value, UUID):
        raise TypeError(f"{name} must be a uuid.UUID, got {type(value).__name__}")
    return value


def check_mode_route(
    mode: TransferMode | str,
    source_id: UUID,
    source_role: SiteRole | str,
    destination_id: UUID,
    destination_role: SiteRole | str,
    route_enabled: bool,
) -> ModeRouteDecision:
    """Return the first failing topology check for one directed route, in section 13.2 order.

    All arguments are validated before any route rule is applied.
    """
    mode_v = _as_enum(mode, TransferMode, "mode")
    source_v = _require_uuid(source_id, "source_id")
    source_role_v = _as_enum(source_role, SiteRole, "source_role")
    destination_v = _require_uuid(destination_id, "destination_id")
    destination_role_v = _as_enum(destination_role, SiteRole, "destination_role")
    if not isinstance(route_enabled, bool):
        raise TypeError(f"route_enabled must be a bool, got {type(route_enabled).__name__}")

    if source_v == destination_v:
        return ModeRouteDecision(False, RouteDecisionReason.SELF_TRANSFER)
    if not route_enabled:
        return ModeRouteDecision(False, RouteDecisionReason.ROUTE_DISABLED)
    if destination_role_v is not SiteRole.BENEFICIARY:
        return ModeRouteDecision(False, RouteDecisionReason.DESTINATION_NOT_BENEFICIARY)
    if mode_v is TransferMode.HUB_ONLY and source_role_v is not SiteRole.HUB:
        return ModeRouteDecision(False, RouteDecisionReason.ORIGIN_NOT_ALLOWED_BY_MODE)
    # HUB_AND_PANTRY: both HUB and BENEFICIARY origins pass the topology check.
    return ModeRouteDecision(True, RouteDecisionReason.MODE_ROUTE_ALLOWED)
