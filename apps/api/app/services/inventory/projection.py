"""Pure dated FEFO and lost-sales projection over explicitly supplied frozen inputs.

No DB access, stock writes, forecast inference, donor-budget or route decisions.
Expired/held stock stays physical, but cannot serve demand or commitments.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date
from typing import Literal
from uuid import UUID

from app.schemas.projection import ProjectionInput
from app.schemas.projection import ProjectionLot as OperationalProjectionLot
from app.services.demand_targets import round_daily_targets
from app.services.inventory.contracts import local_day
from app.services.inventory.experimental_projection import (
    ProjectionDay as ProjectionDay,
)
from app.services.inventory.experimental_projection import (
    ProjectionLot as ProjectionLot,
)
from app.services.inventory.experimental_projection import (
    project_daily as project_daily,
)

ExclusionReason = Literal[
    "EXPIRED", "HELD", "INELIGIBLE", "UNKNOWN_ELIGIBILITY", "UNKNOWN_EXPIRY", "NOT_ARRIVED"
]


@dataclass(frozen=True, slots=True)
class LotQuantity:
    lot_id: UUID
    quantity: int


@dataclass(frozen=True, slots=True)
class ExcludedLot:
    lot_id: UUID
    quantity: int
    reason: ExclusionReason


@dataclass(frozen=True, slots=True)
class OperationalProjectionDay:
    day: date
    demand: int
    arrivals: int
    expired: int
    outbound: int
    served: int
    unmet: int
    eligible_end: int
    physical_end: int
    service: tuple[LotQuantity, ...]
    commitments: tuple[LotQuantity, ...]
    exclusions: tuple[ExcludedLot, ...]
    pending_arrivals: tuple[ExcludedLot, ...]
    remaining: tuple[LotQuantity, ...]


@dataclass(frozen=True, slots=True)
class ProjectionResult:
    inputs: ProjectionInput
    input_hash: str
    days: tuple[OperationalProjectionDay, ...]
    total_unmet: int
    first_deficit_on: date | None


def _reason(lot: OperationalProjectionLot, day: date) -> ExclusionReason | None:
    if lot.expiry.kind == "DATED" and lot.expiry.expires_on < day:
        return "EXPIRED"
    if lot.eligibility != "ELIGIBLE":
        return {"HELD": "HELD", "INELIGIBLE": "INELIGIBLE",
                "UNKNOWN": "UNKNOWN_ELIGIBILITY"}[lot.eligibility]
    if lot.expiry.kind == "UNKNOWN":
        return "UNKNOWN_EXPIRY"
    return None


def _canonical(data: ProjectionInput) -> ProjectionInput:
    # Revalidate even model_construct/model_copy input; caller cannot bypass checks
    # by mutating a supposedly validated Pydantic instance.
    checked = ProjectionInput.model_validate(data.model_dump(mode="python"))
    return checked.model_copy(update={
        "lots": tuple(sorted(checked.lots, key=lambda lot: str(lot.lot_id))),
        "commitments": tuple(sorted(checked.commitments, key=lambda c: str(c.commitment_id))),
    })


def _fingerprint(data: ProjectionInput) -> str:
    payload = data.model_dump(mode="json")
    for item, lot in zip(payload["lots"], data.lots, strict=True):
        item["available_at"] = lot.available_at.astimezone(UTC).isoformat()
    for item, point in zip(payload["demand"], data.demand, strict=True):
        # Exact normalized numeric identity, independent of Decimal context/scale.
        sign, digits, exponent = point.estimate.as_tuple()
        digits = list(digits)
        if not any(digits):
            sign, digits, exponent = 0, [0], 0
        else:
            while digits[-1] == 0:
                digits.pop()
                exponent += 1
        item["estimate"] = [sign, digits, exponent]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def project_inventory(data: ProjectionInput) -> ProjectionResult:
    """Compute daily projection; reject impossible commitments without clamping.

    Opening ON_HAND quantities are physical quantities before horizon commitments,
    not already reservation-subtracted availability. CONFIRMED quantities are only
    outstanding, unreceived supply. The caller owns that snapshot consistency.
    """
    if not isinstance(data, ProjectionInput):
        raise TypeError("projection requires a ProjectionInput")
    frozen = _canonical(data)
    lots = {lot.lot_id: lot for lot in frozen.lots}
    arrival_days = {lot.lot_id: local_day(lot.available_at, frozen.timezone)
                    for lot in frozen.lots}
    balances = {lot.lot_id: lot.quantity for lot in frozen.lots if lot.source_kind == "ON_HAND"}
    seen_expired = set()
    ordered = sorted(frozen.lots, key=lambda lot: (
        lot.expiry.kind != "DATED",
        lot.expiry.expires_on or date.max,
        lot.available_at.astimezone(UTC), str(lot.lot_id),
    ))
    targets = round_daily_targets([(point.day, point.estimate) for point in frozen.demand])
    days = []
    for target in targets.points:
        day = target.day
        arrivals = 0
        for lot in frozen.lots:
            if lot.source_kind == "CONFIRMED" and arrival_days[lot.lot_id] == day:
                balances[lot.lot_id] = lot.quantity
                arrivals += lot.quantity
        expired = 0
        for lot_id, balance in balances.items():
            if _reason(lots[lot_id], day) == "EXPIRED" and lot_id not in seen_expired:
                expired += balance
                seen_expired.add(lot_id)
        outbound = []
        for item in frozen.commitments:
            if item.day != day:
                continue
            if (_reason(lots[item.lot_id], day) is not None
                    or balances.get(item.lot_id, 0) < item.quantity):
                raise ValueError(f"unavailable or excessive commitment {item.commitment_id}")
            balances[item.lot_id] -= item.quantity
            outbound.append(LotQuantity(item.lot_id, item.quantity))
        service = []
        outstanding = target.target
        for lot in ordered:
            if not outstanding:
                break
            if _reason(lot, day) is not None:
                continue
            take = min(balances.get(lot.lot_id, 0), outstanding)
            if take:
                balances[lot.lot_id] -= take
                outstanding -= take
                service.append(LotQuantity(lot.lot_id, take))
        exclusions = []
        eligible_end = 0
        for lot_id, balance in balances.items():
            reason = _reason(lots[lot_id], day)
            if reason is None:
                eligible_end += balance
            elif balance:
                exclusions.append(ExcludedLot(lot_id, balance, reason))
        days.append(OperationalProjectionDay(
            day=day, demand=target.target, arrivals=arrivals, expired=expired,
            outbound=sum(item.quantity for item in outbound),
            served=target.target-outstanding, unmet=outstanding,
            eligible_end=eligible_end, physical_end=sum(balances.values()),
            service=tuple(service), commitments=tuple(outbound),
            exclusions=tuple(sorted(exclusions, key=lambda item: str(item.lot_id))),
            pending_arrivals=tuple(
                ExcludedLot(lot.lot_id, lot.quantity, "NOT_ARRIVED")
                for lot in frozen.lots
                if lot.source_kind == "CONFIRMED" and arrival_days[lot.lot_id] > day
            ),
            remaining=tuple(
                LotQuantity(lot_id, balance)
                for lot_id, balance in sorted(balances.items(), key=lambda p: str(p[0]))
            ),
        ))
    return ProjectionResult(
        inputs=frozen, input_hash=_fingerprint(frozen), days=tuple(days),
        total_unmet=sum(day.unmet for day in days),
        first_deficit_on=next((day.day for day in days if day.unmet), None),
    )
