"""OR-local solver-free dated FEFO recurrence; inventory service remains independent."""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class KernelLot:
    id: str
    units: int
    available_on: date
    expires_on: date | None
    received: bool


@dataclass(frozen=True)
class KernelDay:
    day: date
    demand: int
    received: int
    expired: int
    served: int
    unmet: int
    on_hand: int


@dataclass(frozen=True)
class KernelTrajectory:
    lot: KernelLot
    consumed: tuple[int, ...]
    expired: tuple[int, ...]
    end_balances: tuple[int, ...]


def project_kernel(points: tuple[tuple[date, int], ...], lots: tuple[KernelLot, ...]):
    if len({lot.id for lot in lots}) != len(lots):
        raise ValueError("Duplicate modeled lot identity")
    lots = tuple(sorted(lots, key=lambda x: (x.expires_on or date.max, x.available_on, x.id)))
    balances = {lot.id: lot.units for lot in lots}
    consumption = {lot.id: [] for lot in lots}
    losses = {lot.id: [] for lot in lots}
    endings = {lot.id: [] for lot in lots}
    days = []
    for day, demand in points:
        remaining, expired = demand, 0
        for lot in lots:
            used = lost = 0
            if lot.available_on <= day:
                if lot.expires_on is not None and lot.expires_on < day:
                    lost, balances[lot.id] = balances[lot.id], 0
                else:
                    used = min(balances[lot.id], remaining)
                    balances[lot.id] -= used
                    remaining -= used
            expired += lost
            consumption[lot.id].append(used)
            losses[lot.id].append(lost)
            endings[lot.id].append(balances[lot.id] if lot.available_on <= day else 0)
        days.append(
            KernelDay(
                day,
                demand,
                sum(lot.units for lot in lots if lot.received and lot.available_on == day),
                expired,
                demand - remaining,
                remaining,
                sum(balances[lot.id] for lot in lots if lot.available_on <= day),
            )
        )
    trajectories = tuple(
        KernelTrajectory(
            lot, tuple(consumption[lot.id]), tuple(losses[lot.id]), tuple(endings[lot.id])
        )
        for lot in lots
    )
    return tuple(days), trajectories
