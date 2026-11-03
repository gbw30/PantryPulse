"""Independent small exhaustive oracle for offline projection, not live API evidence."""

import random
from datetime import timedelta
from functools import lru_cache
from itertools import product
from uuid import UUID

import pytest

from app.services.forecasting.handoff import DemandChoice, freeze_handoff
from app.services.forecasting.preparation import prepare
from app.services.forecasting.service import forecast
from app.services.inventory.projection import ProjectionLot, project_daily

from .conftest import AS_OF, CUTOFF, KEY, demand


def exhaustive_service(targets, lots, first):
    """Enumerate all legal lot consumption choices; maximize service day by day.

    This oracle neither imports FEFO helpers nor copies the production lot loop.
    Small bounded stock makes exhaustive enumeration practical.
    """
    admitted = tuple(lot for lot in lots if lot.eligibility == "ELIGIBLE")

    @lru_cache(None)
    def best(day, balances):
        if day == len(targets):
            return ()
        current = first + timedelta(days=day)
        limits = tuple(
            balance
            if lot.available_on <= current
            and (lot.expires_on is None or current < lot.expires_on)
            else 0
            for lot, balance in zip(admitted, balances, strict=True)
        )
        choices = (
            allocation
            for allocation in product(*(range(limit + 1) for limit in limits))
            if sum(allocation) <= targets[day]
        )
        return max(
            (sum(allocation),)
            + best(day + 1, tuple(b - a for b, a in zip(balances, allocation, strict=True)))
            for allocation in choices
        )

    return best(0, tuple(lot.units for lot in admitted))


@pytest.mark.parametrize("seed", range(20))
def test_projection_matches_exhaustive_oracle_and_conserves_units(history, policy, seed):
    rng = random.Random(seed)
    targets = [rng.randrange(4) for _ in range(7)]
    rows = [
        demand(CUTOFF - timedelta(days=6 - i), value, value, 0)
        for i, value in enumerate(targets)
    ]
    inputs = prepare(
        history(rows), data_cutoff_date=CUTOFF, snapshot_as_of=AS_OF, policy=policy
    )
    planned = freeze_handoff(
        inputs, forecast(inputs), choices=(DemandChoice(key=KEY, mode="CENTRAL"),)
    ).selected[0]
    assert [day.units for day in planned.days] == targets
    first = planned.days[0].day
    lots = tuple(
        ProjectionLot(
            lot_id=UUID(int=i + 1),
            key=KEY,
            source_version="oracle-v1",
            unit="meal",
            units=rng.randrange(4),
            available_on=first + timedelta(days=(offset := rng.randrange(4))),
            expires_on=first + timedelta(days=rng.randrange(9)) if i != 0 else None,
            eligibility=rng.choice(["ELIGIBLE", "ELIGIBLE", "HELD", "UNKNOWN"]),
            supply_kind="ON_HAND" if offset == 0 else "CONFIRMED",
        )
        for i in range(3)
    )
    before = tuple(lot.model_dump_json() for lot in lots)
    result = project_daily(planned, lots=lots)
    assert tuple(day.served for day in result) == exhaustive_service(targets, lots, first)
    previous = sum(
        lot.units for lot in lots if lot.eligibility == "ELIGIBLE" and lot.supply_kind == "ON_HAND"
    )
    for day in result:
        assert day.served + day.unmet == day.demand
        assert previous + day.received == day.served + day.expired + day.on_hand
        assert min(day.served, day.unmet, day.on_hand, day.expired) >= 0
        previous = day.on_hand
    assert tuple(lot.model_dump_json() for lot in lots) == before
