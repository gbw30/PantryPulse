"""Hand-computed #23 examples; projection is separate from stock mutation."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from random import Random
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.schemas.projection import (
    OutboundCommitment,
    ProjectionDemand,
    ProjectionInput,
    ProjectionLot,
)
from app.services.inventory.projection import project_inventory

D1 = date(2026, 10, 24)
D2 = D1 + timedelta(days=1)
D3 = D2 + timedelta(days=1)


def uid(n):
    return UUID(int=n)


def instant(day, hour=0):
    return datetime(day.year, day.month, day.day, hour, tzinfo=UTC)


def lot(n=1, quantity=40, **changes):
    values = dict(
        lot_id=uid(n), organization_id=uid(100), site_id=uid(101), product_id=uid(102),
        base_unit="meal", quantity=quantity, source_kind="ON_HAND", source_id=f"stock-{n}",
        source_version="1", available_at=instant(D1), eligibility="ELIGIBLE",
        expiry={"kind": "NON_EXPIRING", "expires_on": None},
    )
    values.update(changes)
    return ProjectionLot(**values)


def request(lots=(), estimates=(50, 40), commitments=(), **changes):
    values = dict(
        policy_version="projection-v1", snapshot_id=uid(200), organization_id=uid(100),
        site_id=uid(101), product_id=uid(102), base_unit="meal", timezone="UTC",
        calendar_version_id=uid(201), inventory_version=1, opening_on=D1,
        forecast_id=uid(202), provider="fixture", planning_mode="CENTRAL",
        transfer_mode="HUB_ONLY",
        assumptions=("SIMULATED",), lots=tuple(lots), commitments=tuple(commitments),
        demand=tuple(ProjectionDemand(day=D1 + timedelta(days=i), estimate=Decimal(str(q)))
                     for i, q in enumerate(estimates)),
    )
    values.update(changes)
    return ProjectionInput(**values)


def commitment(n=1, quantity=10, day=D1, lot_id=None):
    return OutboundCommitment(
        commitment_id=uid(300+n), lot_id=lot_id or uid(1), day=day, quantity=quantity,
        source_version="1",
    )


def test_golden_lost_sales_not_repeated_negative_balance():
    result = project_inventory(request([lot()]))
    assert [(d.served, d.unmet, d.eligible_end) for d in result.days] == [(40, 10, 0), (0, 40, 0)]
    assert result.total_unmet == 50
    assert result.first_deficit_on == D1


def test_late_confirmed_arrival_cannot_repair_yesterday():
    incoming = lot(source_kind="CONFIRMED", source_id="supply-1", available_at=instant(D2))
    result = project_inventory(request([incoming]))
    assert [(d.arrivals, d.served, d.unmet) for d in result.days] == [(0, 0, 50), (40, 40, 0)]


def test_round_each_day_before_summing_and_preserve_input():
    data = request([lot(quantity=1)], estimates=("0.2", "0.2"))
    before = data.model_dump_json()
    result = project_inventory(data)
    assert [d.demand for d in result.days] == [1, 1]
    assert result.total_unmet == 1
    assert data.model_dump_json() == before
    assert project_inventory(data) == result


def test_expiry_is_inclusive_then_unavailable_without_disposal():
    result = project_inventory(request([
        lot(quantity=10, expiry={"kind": "DATED", "expires_on": D1})
    ], estimates=(3, 3)))
    assert [(d.served, d.expired, d.physical_end, d.eligible_end) for d in result.days] == [
        (3, 0, 7, 7), (0, 7, 7, 0),
    ]
    assert result.days[1].exclusions[0].reason == "EXPIRED"


def test_fefo_is_hard_even_if_input_order_is_reversed():
    early = lot(1, 5, expiry={"kind": "DATED", "expires_on": D1})
    late = lot(2, 5, expiry={"kind": "DATED", "expires_on": D3})
    forever = lot(3, 5)
    result = project_inventory(request([forever, late, early], estimates=(7,)))
    assert [(a.lot_id, a.quantity) for a in result.days[0].service] == [(uid(1), 5), (uid(2), 2)]


@pytest.mark.parametrize("eligibility,expiry,reason", [
    ("HELD", {"kind": "NON_EXPIRING", "expires_on": None}, "HELD"),
    ("UNKNOWN", {"kind": "NON_EXPIRING", "expires_on": None}, "UNKNOWN_ELIGIBILITY"),
    ("INELIGIBLE", {"kind": "NON_EXPIRING", "expires_on": None}, "INELIGIBLE"),
    ("ELIGIBLE", {"kind": "UNKNOWN", "expires_on": None}, "UNKNOWN_EXPIRY"),
])
def test_unavailable_lots_retained_with_reasons(eligibility, expiry, reason):
    result = project_inventory(request([
        lot(eligibility=eligibility, expiry=expiry)
    ], estimates=(10,)))
    assert (result.days[0].served, result.days[0].physical_end) == (0, 40)
    assert result.days[0].exclusions[0].reason == reason


def test_commitments_precede_local_service_and_are_not_subtracted_twice():
    result = project_inventory(request([lot(quantity=20)], estimates=(15, 1),
                                       commitments=[commitment(quantity=8)]))
    assert [(d.outbound, d.served, d.unmet) for d in result.days] == [(8, 12, 3), (0, 0, 1)]


@pytest.mark.parametrize("stock,commit", [
    (lot(quantity=5), commitment(quantity=6)),
    (lot(eligibility="HELD"), commitment()),
    (lot(expiry={"kind": "DATED", "expires_on": D1}), commitment(day=D2)),
    (lot(source_kind="CONFIRMED", available_at=instant(D2)), commitment()),
])
def test_unavailable_or_excessive_commitment_rejected(stock, commit):
    with pytest.raises(ValueError, match="commitment"):
        project_inventory(request([stock], commitments=[commit]))


def test_confirmed_arrival_local_date_uses_site_timezone():
    # 01:00 UTC October 25 is still October 24 in New York.
    incoming = lot(source_kind="CONFIRMED", available_at=instant(D2, 1))
    result = project_inventory(request([incoming], estimates=(40,), timezone="America/New_York"))
    assert result.days[0].served == 40


def test_zero_demand_and_no_stock_are_valid():
    result = project_inventory(request(estimates=(0, 0)))
    assert result.total_unmet == 0
    assert result.first_deficit_on is None


@pytest.mark.parametrize("changes", [
    {"organization_id": uid(999)}, {"site_id": uid(999)},
    {"product_id": uid(999)}, {"base_unit": "bottle"},
    {"source_kind": "ON_HAND", "available_at": instant(D2)},
])
def test_scope_unit_and_future_opening_stock_rejected(changes):
    with pytest.raises(ValidationError):
        request([lot(**changes)])


def test_duplicate_lot_and_supply_rejected():
    with pytest.raises(ValidationError):
        request([lot(), lot()])
    with pytest.raises(ValidationError):
        request([lot(1, source_kind="CONFIRMED", source_id="supply"),
                 lot(2, source_kind="CONFIRMED", source_id="supply")])


@pytest.mark.parametrize("changes", [
    {"timezone": "Invalid/Zone"}, {"inventory_version": 0},
    {"policy_version": "experimental"}, {"demand": ()},
    {"demand": (ProjectionDemand(day=D1, estimate=Decimal(1)),
                ProjectionDemand(day=D3, estimate=Decimal(1)))},
    {"commitments": (commitment(), commitment())},
    {"commitments": (commitment(lot_id=uid(999)),)},
    {"commitments": (commitment(day=D3),)},
])
def test_invalid_input_rejected(changes):
    with pytest.raises(ValidationError):
        request([lot()], **changes)


@pytest.mark.parametrize("quantity", [-1, True, 0.5, 2**63])
def test_invalid_stock_quantity_rejected(quantity):
    with pytest.raises(ValidationError):
        lot(quantity=quantity)


@pytest.mark.parametrize("estimate", [Decimal("NaN"), Decimal("Infinity"), Decimal(-1), None])
def test_missing_or_invalid_demand_not_silently_zero(estimate):
    with pytest.raises(ValidationError):
        ProjectionDemand(day=D1, estimate=estimate)


def test_canonical_replay_independent_of_lot_and_commitment_order():
    lots = [lot(1), lot(2)]
    commits = [commitment(1, lot_id=uid(1)), commitment(2, lot_id=uid(2))]
    a = project_inventory(request(lots, commitments=commits))
    b = project_inventory(request(lots[::-1], commitments=commits[::-1]))
    assert a == b
    assert len(a.input_hash) == 64
    changed = project_inventory(request(lots, estimates=(51, 40), commitments=commits))
    assert changed.input_hash != a.input_hash


def test_dated_maximum_expiry_precedes_non_expiring_stock():
    result = project_inventory(request([
        lot(1, 5), lot(2, 5, expiry={"kind": "DATED", "expires_on": date.max})
    ], estimates=(3,)))
    assert result.days[0].service[0].lot_id == uid(2)


def test_committed_stock_consumed_on_prior_day_is_rejected_not_clamped():
    with pytest.raises(ValueError, match="commitment"):
        project_inventory(request([lot(quantity=10)], estimates=(10, 0),
                                  commitments=[commitment(day=D2)]))


def test_multiple_commitments_cannot_overdraw_together():
    with pytest.raises(ValueError, match="commitment"):
        project_inventory(request([lot(quantity=15)],
                                  commitments=[commitment(1), commitment(2)]))


def test_expired_arrival_and_future_supply_are_not_usable():
    result = project_inventory(request([
        lot(1, 5, source_kind="CONFIRMED", available_at=instant(D2),
            expiry={"kind": "DATED", "expires_on": D1}),
        lot(2, 7, source_kind="CONFIRMED", available_at=instant(D3)),
    ]))
    assert [d.served for d in result.days] == [0, 0]
    assert [d.expired for d in result.days] == [0, 5]
    assert result.days[-1].physical_end == 5
    assert [(p.lot_id, p.quantity, p.reason) for p in result.days[-1].pending_arrivals] == [
        (uid(2), 7, "NOT_ARRIVED")
    ]


def test_expiry_is_not_counted_again_on_following_days():
    result = project_inventory(request([
        lot(1, 9, expiry={"kind": "DATED", "expires_on": D1})
    ], estimates=(0, 0, 0)))
    assert [d.expired for d in result.days] == [0, 9, 0]


@pytest.mark.parametrize("zone,arrival,expected", [
    # Fall DST transition: both 01:30 local instants belong to November 1.
    ("America/New_York", datetime(2026, 11, 1, 5, 30, tzinfo=UTC), 10),
    ("America/New_York", datetime(2026, 11, 1, 6, 30, tzinfo=UTC), 10),
])
def test_dst_instants_map_to_one_operational_day(zone, arrival, expected):
    opening = date(2026, 11, 1)
    data = request([lot(source_kind="CONFIRMED", available_at=arrival)],
                   opening_on=opening, timezone=zone,
                   demand=(ProjectionDemand(day=opening, estimate=Decimal(10)),))
    assert project_inventory(data).days[0].served == expected


def test_on_hand_past_utc_midnight_can_still_belong_to_opening_local_day():
    result = project_inventory(request([
        lot(available_at=instant(D2, 1))
    ], estimates=(10,), timezone="America/New_York"))
    assert result.days[0].served == 10


@pytest.mark.parametrize("changes", [
    {"demand": (ProjectionDemand(day=D1, estimate=Decimal(0)),) * 2},
    {"demand": tuple(ProjectionDemand(day=D1+timedelta(days=i), estimate=Decimal(0))
                     for i in range(8))},
    {"transfer_mode": None}, {"transfer_mode": "default"},
])
def test_duplicate_dates_horizon_and_mode_rejected(changes):
    with pytest.raises(ValidationError):
        request(**changes)


def test_unsafe_model_copy_is_revalidated_at_service_boundary():
    data = request([lot()]).model_copy(update={"inventory_version": 0})
    with pytest.raises(ValidationError):
        project_inventory(data)


def test_naive_arrival_and_huge_demand_rejected():
    with pytest.raises(ValidationError):
        lot(available_at=datetime(2026, 10, 24))
    with pytest.raises(ValidationError):
        ProjectionDemand(day=D1, estimate=Decimal(2**63))


def test_numeric_scale_and_timestamp_offset_do_not_change_identity():
    from datetime import timezone

    first = request([lot()], estimates=("1.00", "0.0"))
    same_instant = instant(D1).astimezone(timezone(timedelta(hours=-4)))
    second = request([lot(available_at=same_instant)], estimates=("1", "-0"))
    assert project_inventory(first).input_hash == project_inventory(second).input_hash


@pytest.mark.parametrize("field,value", [
    ("inventory_version", 2), ("provider", "fallback"),
    ("transfer_mode", "HUB_AND_PANTRY"), ("calendar_version_id", uid(999)),
    ("assumptions", ("SIMULATED", "modified")),
])
def test_changed_provenance_or_policy_changes_projection_identity(field, value):
    assert project_inventory(request()).input_hash != project_inventory(
        request(**{field: value})
    ).input_hash


def test_seeded_conservation_and_fefo_against_independent_daily_oracle():
    rng = Random(2301)
    for _ in range(100):
        # Independent oracle: simple dated opening lots, no model/service helpers.
        counts = [rng.randrange(20) for _ in range(4)]
        expiry_offsets = [rng.randrange(-1, 5) for _ in counts]
        demand = [rng.randrange(25) for _ in range(4)]
        lots = [lot(i+1, q, expiry={"kind": "DATED", "expires_on":
                                   D1+timedelta(days=expiry_offsets[i])})
                for i, q in enumerate(counts)]
        result = project_inventory(request(lots, estimates=demand))
        remaining = counts[:]
        total_service = 0
        for offset, row in enumerate(result.days):
            need = demand[offset]
            allocations = []
            for i in sorted(range(4), key=lambda i: (expiry_offsets[i], i)):
                if expiry_offsets[i] < offset:
                    continue
                used = min(need, remaining[i])
                if used:
                    allocations.append((uid(i+1), used))
                remaining[i] -= used
                need -= used
            assert row.unmet == need
            assert [(a.lot_id, a.quantity) for a in row.service] == allocations
            assert row.served + row.unmet == demand[offset]
            assert row.physical_end == sum(remaining)
            assert row.eligible_end == sum(q for i, q in enumerate(remaining)
                                           if expiry_offsets[i] >= offset)
            assert row.physical_end == row.eligible_end + sum(e.quantity for e in row.exclusions)
            total_service += row.served
            assert row.physical_end + total_service == sum(counts)
            assert all(q.quantity >= 0 for q in row.remaining)


def test_commitment_arrival_and_service_conserve_physical_stock_each_day():
    result = project_inventory(request([
        lot(1, 20), lot(2, 12, source_kind="CONFIRMED", available_at=instant(D2))
    ], estimates=(5, 20, 10), commitments=[commitment(quantity=7)]))
    previous = 20
    for row in result.days:
        assert row.physical_end == previous + row.arrivals - row.outbound - row.served
        previous = row.physical_end
    assert [row.unmet for row in result.days] == [0, 0, 10]


def test_lot_expiry_version_or_commitment_change_changes_identity():
    base = project_inventory(request([lot()], estimates=(0,)))
    variants = [
        request([lot(source_version="2")], estimates=(0,)),
        request([lot(expiry={"kind": "DATED", "expires_on": D2})], estimates=(0,)),
        request([lot()], estimates=(0,), commitments=[commitment()]),
    ]
    assert all(project_inventory(v).input_hash != base.input_hash for v in variants)


def test_transfer_mode_is_required_and_both_modes_preserve_local_loss_arithmetic():
    data = request([lot()]).model_dump()
    del data["transfer_mode"]
    with pytest.raises(ValidationError):
        ProjectionInput(**data)
    for mode in ("HUB_ONLY", "HUB_AND_PANTRY"):
        result = project_inventory(request([lot()], transfer_mode=mode))
        assert result.total_unmet == 50
        assert result.inputs.transfer_mode == mode


def test_result_and_nested_inputs_are_immutable():
    from dataclasses import FrozenInstanceError

    result = project_inventory(request([lot()]))
    with pytest.raises(FrozenInstanceError):
        result.days[0].served = 0
    with pytest.raises(ValidationError):
        result.inputs.lots[0].quantity = 0


def test_no_reservation_or_unknown_fields_can_be_silently_applied():
    data = lot().model_dump()
    data["reserved"] = 5
    with pytest.raises(ValidationError):
        ProjectionLot(**data)
