from datetime import timedelta
from uuid import UUID

import pytest

from app.services.forecasting.handoff import DemandChoice, freeze_handoff, verify_handoff
from app.services.forecasting.schemas import SeriesScope
from app.services.forecasting.service import forecast
from app.services.inventory.projection import ProjectionLot, project_daily

from .conftest import CUTOFF, KEY, demand
from .test_core import frozen


def handoff(history, policy, **choice):
    inputs = frozen(history(), policy)
    output = forecast(inputs)
    return freeze_handoff(
        inputs, output, choices=(DemandChoice(key=KEY, mode="CENTRAL", **choice),)
    )


def test_handoff_is_frozen_and_buffer_is_explicit(history, policy):
    inputs = frozen(history(), policy)
    output = forecast(inputs)
    with pytest.raises(ValueError, match="explicit buffer"):
        freeze_handoff(inputs, output, choices=(DemandChoice(key=KEY, mode="CONSERVATIVE"),))
    result = freeze_handoff(
        inputs,
        output,
        choices=(
            DemandChoice(
                key=KEY,
                mode="CONSERVATIVE",
                buffer_fraction=0.1,
            ),
        ),
    )
    assert result.selected[0].days[0].units == 18
    assert result.selected[0].days[0].method == "EXPLICIT_BUFFER"
    assert output.series[0].points[0].p90 is None
    verify_handoff(result)
    with pytest.raises(ValueError, match="hash"):
        verify_handoff(result.model_copy(update={"content_hash": "bad"}))


def test_partial_handoff_requires_explicit_exclusions(history, policy):
    bundle = history()
    other = KEY.model_copy(update={"site_id": UUID(int=99)})
    bundle = bundle.model_copy(
        update={
            "scope": (
                *bundle.scope,
                SeriesScope(
                    key=other,
                    unit="meal",
                    timezone="America/New_York",
                ),
            )
        }
    )
    inputs = frozen(bundle, policy)
    output = forecast(inputs)
    assert not output.ready_for_publication
    choice = (DemandChoice(key=KEY, mode="CENTRAL"),)
    with pytest.raises(ValueError, match="explicitly declared"):
        freeze_handoff(inputs, output, choices=choice)
    with pytest.raises(ValueError, match="opt-in"):
        freeze_handoff(inputs, output, choices=choice, excluded_demand=(other,))
    result = freeze_handoff(
        inputs, output, choices=choice, excluded_demand=(other,), allow_partial_scope=True
    )
    assert result.partial_scope


def test_daily_ceiling_precedes_aggregation_without_float_boundary_error(history, policy):
    rows = [demand(CUTOFF - timedelta(days=i), 100, 100, 0) for i in range(7)]
    inputs = frozen(history(rows), policy)
    result = freeze_handoff(
        inputs,
        forecast(inputs),
        choices=(
            DemandChoice(
                key=KEY,
                mode="CONSERVATIVE",
                buffer_fraction=0.1,
            ),
        ),
    )
    assert [day.units for day in result.selected[0].days] == [110] * 7


def lot(identifier, quantity, *, day=CUTOFF, expiry=None, kind="ON_HAND", eligibility="ELIGIBLE"):
    return ProjectionLot(
        lot_id=UUID(int=identifier),
        key=KEY,
        source_version="v1",
        unit="meal",
        units=quantity,
        available_on=day,
        expires_on=expiry,
        eligibility=eligibility,
        supply_kind=kind,
    )


def test_lost_sales_late_arrival_does_not_repair_previous_unmet(history, policy):
    rows = [demand(CUTOFF - timedelta(days=i), 0, 0, 0) for i in range(7)]
    rows[-1] = demand(CUTOFF - timedelta(days=6), 50, 50, 0)
    rows[-2] = demand(CUTOFF - timedelta(days=5), 40, 40, 0)
    planned = handoff(lambda: history(rows), policy).selected[0]
    baseline = project_daily(planned, lots=(lot(1, 40),))
    assert sum(day.unmet for day in baseline) == 50
    later = project_daily(
        planned,
        lots=(
            lot(1, 40),
            lot(
                2,
                100,
                day=CUTOFF + timedelta(days=2),
                kind="CONFIRMED",
            ),
        ),
    )
    assert [day.unmet for day in later[:2]] == [10, 0]
    assert later[1].received == 100


def test_expiry_fefo_eligibility_and_double_counting(history, policy):
    planned = handoff(history, policy).selected[0]
    lots = (
        lot(1, 10, expiry=CUTOFF + timedelta(days=2)),
        lot(2, 50),
        lot(3, 100, eligibility="UNKNOWN"),
    )
    projected = project_daily(planned, lots=lots)
    assert projected[1].expired == 0  # Earlier lot was served first on day one.
    assert sum(day.served for day in projected) == 60
    with pytest.raises(ValueError, match="counted twice"):
        project_daily(planned, lots=(lots[0], lots[0]))
    expired = project_daily(planned, lots=(lot(1, 100, expiry=CUTOFF + timedelta(days=1)),))
    assert expired[0].served == 0 and expired[0].expired == 100
