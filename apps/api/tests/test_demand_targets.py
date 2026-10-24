"""BE-03 (BACKEND-SPEC.md section 13.3): round dated demand before aggregation.

Expected values below are written by hand from the specification table and from
ordinary arithmetic; they are not derived from the implementation.
"""

import copy
import math
from datetime import date, datetime
from decimal import Context, Decimal, Inexact, Rounded, localcontext

import pytest

from app.services.demand_targets import (
    RoundedDailyTarget,
    RoundedDemandTargets,
    round_daily_targets,
)

D1 = date(2026, 10, 26)
D2 = date(2026, 10, 27)
D3 = date(2026, 10, 28)


def _pairs(result: RoundedDemandTargets) -> list[tuple[date, int]]:
    return [(p.day, p.target) for p in result.points]


# --- Specification table -----------------------------------------------------


def test_table_row_zero_two_and_just_above_two():
    result = round_daily_targets([(D1, Decimal("0")), (D2, Decimal("2")), (D3, Decimal("2.0001"))])
    assert _pairs(result) == [(D1, 0), (D2, 2), (D3, 3)]
    assert result.total_target == 5


def test_table_row_rounds_each_day_before_summing():
    result = round_daily_targets([(D1, Decimal("0.2")), (D2, Decimal("0.2"))])
    assert _pairs(result) == [(D1, 1), (D2, 1)]
    # Not ceil(0.4) == 1.
    assert result.total_target == 2


def test_table_row_tiny_excess_over_one_rounds_up_to_two():
    result = round_daily_targets([(D1, Decimal("1.0000000000000000000000000001"))])
    assert _pairs(result) == [(D1, 2)]
    assert result.total_target == 2


# --- Exact semantics independent of the active Decimal context ----------------


def test_ceiling_is_exact_under_low_precision_context():
    with localcontext() as ctx:
        ctx.prec = 2
        result = round_daily_targets(
            [
                (D1, Decimal("1.0000000000000000000000000001")),
                (D2, Decimal("12345.0001")),
                (D3, Decimal("999.5")),
            ]
        )
    assert _pairs(result) == [(D1, 2), (D2, 12346), (D3, 1000)]
    assert result.total_target == 2 + 12346 + 1000


def test_ceiling_is_exact_with_inexact_and_rounded_traps_enabled():
    strict = Context(prec=1, traps=[Inexact, Rounded])
    with localcontext(strict):
        result = round_daily_targets([(D1, Decimal("7.01")), (D2, Decimal("80"))])
    assert _pairs(result) == [(D1, 8), (D2, 80)]
    assert result.total_target == 88


def test_integral_values_with_trailing_zeros_are_not_bumped():
    result = round_daily_targets([(D1, Decimal("3.000")), (D2, Decimal("4E+1"))])
    assert _pairs(result) == [(D1, 3), (D2, 40)]
    assert result.total_target == 43


def test_zero_stays_zero_including_scaled_and_negative_zero():
    result = round_daily_targets([(D1, Decimal("0")), (D2, Decimal("0.000")), (D3, Decimal("-0"))])
    assert _pairs(result) == [(D1, 0), (D2, 0), (D3, 0)]
    assert result.total_target == 0


def test_targets_and_total_are_python_ints():
    result = round_daily_targets([(D1, Decimal("1.5"))])
    assert type(result.points[0].target) is int
    assert type(result.total_target) is int


# --- Dates, gaps and order -----------------------------------------------------


def test_gaps_are_preserved_and_no_dates_are_manufactured():
    far = date(2026, 11, 2)
    result = round_daily_targets([(D1, Decimal("1.1")), (far, Decimal("0.5"))])
    assert [p.day for p in result.points] == [D1, far]
    assert result.total_target == 3


def test_tuple_input_is_accepted_and_output_points_is_a_tuple():
    result = round_daily_targets(((D1, Decimal("1")),))
    assert isinstance(result.points, tuple)
    assert result.points == (RoundedDailyTarget(day=D1, target=1),)


def test_unordered_dates_are_rejected():
    with pytest.raises(ValueError):
        round_daily_targets([(D2, Decimal("1")), (D1, Decimal("1"))])


def test_duplicate_dates_are_rejected_even_with_equal_values():
    with pytest.raises(ValueError):
        round_daily_targets([(D1, Decimal("1")), (D1, Decimal("1"))])


def test_empty_input_is_rejected():
    with pytest.raises(ValueError):
        round_daily_targets([])


# --- Type rejections -----------------------------------------------------------


@pytest.mark.parametrize("bad", [1.5, 2.0, True, False, "1", 1, None])
def test_non_decimal_estimates_raise_type_error(bad):
    with pytest.raises(TypeError):
        round_daily_targets([(D1, bad)])


@pytest.mark.parametrize("bad_day", [datetime(2026, 10, 26, 0, 0), "2026-10-26", 20261026, None])
def test_non_date_days_raise_type_error(bad_day):
    with pytest.raises(TypeError):
        round_daily_targets([(bad_day, Decimal("1"))])


@pytest.mark.parametrize("bad_points", [None, "", "abc", b"", 5, {D1: Decimal("1")}])
def test_non_sequence_points_raise_type_error(bad_points):
    with pytest.raises(TypeError):
        round_daily_targets(bad_points)


def test_generator_points_raise_type_error():
    with pytest.raises(TypeError):
        round_daily_targets(p for p in [(D1, Decimal("1"))])


@pytest.mark.parametrize("bad_pair", [(D1,), (D1, Decimal("1"), Decimal("2")), D1, "ab"])
def test_malformed_pairs_raise_type_error(bad_pair):
    with pytest.raises(TypeError):
        round_daily_targets([bad_pair])


# --- Value rejections ----------------------------------------------------------


@pytest.mark.parametrize(
    "bad", [Decimal("NaN"), Decimal("sNaN"), Decimal("Infinity"), Decimal("-Infinity")]
)
def test_nonfinite_estimates_raise_value_error(bad):
    with pytest.raises(ValueError):
        round_daily_targets([(D1, bad)])


@pytest.mark.parametrize("bad", [Decimal("-1"), Decimal("-0.0001")])
def test_negative_estimates_raise_value_error(bad):
    with pytest.raises(ValueError):
        round_daily_targets([(D1, bad)])


def test_all_inputs_validated_before_any_result_on_late_bad_row():
    with pytest.raises(ValueError):
        round_daily_targets([(D1, Decimal("1")), (D2, Decimal("2")), (D3, Decimal("-3"))])


# --- Records and nonmutation ---------------------------------------------------


def test_result_records_are_frozen():
    result = round_daily_targets([(D1, Decimal("1"))])
    with pytest.raises(AttributeError):
        result.total_target = 99  # type: ignore[misc]
    with pytest.raises(AttributeError):
        result.points[0].target = 99  # type: ignore[misc]
    with pytest.raises(AttributeError):
        result.points[0].day = D2  # type: ignore[misc]


def test_input_is_not_mutated():
    points = [(D1, Decimal("0.2")), (D2, Decimal("2.0001"))]
    snapshot = copy.deepcopy(points)
    ids = [id(x) for pair in points for x in pair]
    round_daily_targets(points)
    assert points == snapshot
    assert [id(x) for pair in points for x in pair] == ids
    assert [str(v) for _, v in points] == ["0.2", "2.0001"]


def test_total_equals_sum_of_independent_per_day_ceilings():
    raw = ["0.1", "0.9", "1", "1.01", "2.5", "10"]
    days = [date(2026, 10, d) for d in range(1, 7)]
    result = round_daily_targets([(d, Decimal(v)) for d, v in zip(days, raw, strict=True)])
    expected = [1, 1, 1, 2, 3, 10]
    assert [p.target for p in result.points] == expected
    assert result.total_target == 18
    # Contrast: ceiling of the aggregate would be smaller.
    assert math.ceil(sum(Decimal(v) for v in raw)) == 16
