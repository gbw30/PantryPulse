"""BE-06 (BACKEND-SPEC.md section 13.6): align one historical target without imputation.

Expected calendars below are written out by hand; they are not produced by the
implementation under test.
"""

import copy
from datetime import date, datetime
from decimal import Decimal

import pytest

from app.services.forecasting.history import AlignedObservation, align_history

D1 = date(2026, 10, 1)
D2 = date(2026, 10, 2)
D3 = date(2026, 10, 3)


def _rows(result):
    return [(o.day, o.quantity, o.source_present) for o in result]


# --- Core missingness semantics --------------------------------------------------


def test_observed_zero_absent_day_and_explicit_null_are_distinguished():
    result = align_history(D1, D3, [(D1, Decimal("0")), (D3, None)])
    assert _rows(result) == [
        (D1, Decimal(0), True),
        (D2, None, False),
        (D3, None, True),
    ]
    # Explicit null and absence are never turned into zero.
    assert result[1].quantity is None
    assert result[2].quantity is None


def test_result_is_a_tuple_of_aligned_observations():
    result = align_history(D1, D1, [(D1, Decimal("4"))])
    assert isinstance(result, tuple)
    assert result == (AlignedObservation(day=D1, quantity=Decimal("4"), source_present=True),)


def test_unordered_valid_input_is_returned_chronologically():
    obs = [(D3, Decimal("3")), (D1, Decimal("1")), (D2, Decimal("2"))]
    result = align_history(D1, D3, obs)
    assert _rows(result) == [
        (D1, Decimal("1"), True),
        (D2, Decimal("2"), True),
        (D3, Decimal("3"), True),
    ]


def test_empty_source_yields_complete_all_missing_calendar():
    result = align_history(D1, date(2026, 10, 5), [])
    assert _rows(result) == [(date(2026, 10, d), None, False) for d in range(1, 6)]


def test_single_day_interval_with_no_rows():
    assert _rows(align_history(D2, D2, [])) == [(D2, None, False)]


def test_interval_across_month_and_leap_day():
    start = date(2028, 2, 28)
    cutoff = date(2028, 3, 1)
    result = align_history(start, cutoff, [(date(2028, 2, 29), Decimal("7"))])
    assert _rows(result) == [
        (date(2028, 2, 28), None, False),
        (date(2028, 2, 29), Decimal("7"), True),
        (date(2028, 3, 1), None, False),
    ]


def test_no_forecast_dates_are_appended_after_cutoff():
    result = align_history(D1, D2, [(D1, Decimal("1"))])
    assert [o.day for o in result] == [D1, D2]


def test_tuple_observations_and_list_pairs_are_accepted():
    result = align_history(D1, D2, ([D2, Decimal("5")],))
    assert _rows(result) == [(D1, None, False), (D2, Decimal("5"), True)]


# --- Exact Decimal retention -------------------------------------------------------


def test_supplied_decimals_are_retained_exactly():
    a = Decimal("2.50")
    b = Decimal("0.000")
    c = Decimal("1E+3")
    d = Decimal("0.1234567890123456789012345678901234567890")
    start = D1
    cutoff = date(2026, 10, 4)
    result = align_history(start, cutoff, [(D1, a), (D2, b), (D3, c), (cutoff, d)])
    got = [o.quantity for o in result]
    assert [str(q) for q in got] == ["2.50", "0.000", "1E+3", str(d)]
    assert [q.as_tuple() for q in got] == [x.as_tuple() for x in (a, b, c, d)]


# --- Row rejections -----------------------------------------------------------------


def test_duplicate_days_rejected_even_when_values_match():
    with pytest.raises(ValueError):
        align_history(D1, D3, [(D2, Decimal("1")), (D2, Decimal("1"))])


def test_duplicate_days_rejected_when_one_is_null():
    with pytest.raises(ValueError):
        align_history(D1, D3, [(D2, None), (D2, Decimal("1"))])


def test_row_before_start_is_rejected():
    with pytest.raises(ValueError):
        align_history(D2, D3, [(D1, Decimal("1"))])


def test_future_row_after_cutoff_is_rejected_not_dropped():
    with pytest.raises(ValueError):
        align_history(D1, D2, [(D1, Decimal("1")), (D3, Decimal("9"))])


def test_future_null_row_after_cutoff_is_rejected():
    with pytest.raises(ValueError):
        align_history(D1, D2, [(D3, None)])


# --- Boundary rejections --------------------------------------------------------------


def test_start_after_cutoff_is_rejected():
    with pytest.raises(ValueError):
        align_history(D3, D1, [])


@pytest.mark.parametrize("bad", [datetime(2026, 10, 1), "2026-10-01", None, 20261001])
def test_non_date_start_raises_type_error(bad):
    with pytest.raises(TypeError):
        align_history(bad, D3, [])


@pytest.mark.parametrize("bad", [datetime(2026, 10, 3), "2026-10-03", None, 20261003])
def test_non_date_cutoff_raises_type_error(bad):
    with pytest.raises(TypeError):
        align_history(D1, bad, [])


# --- Type rejections for observations ---------------------------------------------------


@pytest.mark.parametrize("bad", [1.0, 0.0, True, False, 1, 0, "1"])
def test_non_decimal_quantity_raises_type_error(bad):
    with pytest.raises(TypeError):
        align_history(D1, D3, [(D1, bad)])


@pytest.mark.parametrize("bad_day", [datetime(2026, 10, 1, 12), "2026-10-01", None, 1])
def test_non_date_observation_day_raises_type_error(bad_day):
    with pytest.raises(TypeError):
        align_history(D1, D3, [(bad_day, Decimal("1"))])


@pytest.mark.parametrize(
    "bad_pair", [(D1,), (D1, Decimal("1"), True), D1, Decimal("1"), "ab", None]
)
def test_malformed_pairs_raise_type_error(bad_pair):
    with pytest.raises(TypeError):
        align_history(D1, D3, [bad_pair])


@pytest.mark.parametrize("bad_obs", [None, "", "abc", b"", 5, {D1: Decimal("1")}])
def test_non_sequence_observations_raise_type_error(bad_obs):
    with pytest.raises(TypeError):
        align_history(D1, D3, bad_obs)


def test_generator_observations_raise_type_error():
    with pytest.raises(TypeError):
        align_history(D1, D3, (pair for pair in [(D1, Decimal("1"))]))


# --- Value rejections for observations ---------------------------------------------------


@pytest.mark.parametrize(
    "bad", [Decimal("NaN"), Decimal("sNaN"), Decimal("Infinity"), Decimal("-Infinity")]
)
def test_nonfinite_quantity_raises_value_error(bad):
    with pytest.raises(ValueError):
        align_history(D1, D3, [(D1, bad)])


@pytest.mark.parametrize("bad", [Decimal("-1"), Decimal("-0.0001")])
def test_negative_quantity_raises_value_error(bad):
    with pytest.raises(ValueError):
        align_history(D1, D3, [(D1, bad)])


def test_late_invalid_row_rejects_whole_input():
    with pytest.raises(ValueError):
        align_history(D1, D3, [(D1, Decimal("1")), (D2, Decimal("2")), (D3, Decimal("-1"))])


# --- Records and nonmutation -------------------------------------------------------------


def test_aligned_observations_are_frozen():
    result = align_history(D1, D1, [(D1, Decimal("1"))])
    with pytest.raises(AttributeError):
        result[0].quantity = Decimal("2")  # type: ignore[misc]
    with pytest.raises(AttributeError):
        result[0].source_present = False  # type: ignore[misc]
    with pytest.raises(AttributeError):
        result[0].day = D2  # type: ignore[misc]


def test_input_is_not_mutated():
    obs = [(D3, None), (D1, Decimal("0.50"))]
    snapshot = copy.deepcopy(obs)
    ids = [id(x) for pair in obs for x in pair]
    align_history(D1, D3, obs)
    assert obs == snapshot
    assert [id(x) for pair in obs for x in pair] == ids
    assert obs[0] == (D3, None)
    assert str(obs[1][1]) == "0.50"
