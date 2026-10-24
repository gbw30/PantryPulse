"""BE-04 (BACKEND-SPEC.md section 13.4): exact fixed-point floor primitive.

Expected values are hand-written; the boundary property is checked with exact Fraction
comparisons, independent of how the implementation computes the floor.
"""

import inspect
from decimal import Decimal
from fractions import Fraction

import pytest

from app.services.fixed_point import quantize_weighted_deficit

INT64_MAX = 9223372036854775807
SCALE = 10000


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Fraction(0), 0),
        (Fraction(1, 3), 3333),
        (Fraction(1, 20000), 0),
        (Fraction(9999, 10000), 9999),
        (Fraction(1), 10000),
        (Fraction(10001, 10000), 10001),
        (Fraction(2, 3), 6666),
        (Fraction(1, 10000), 1),
        (Fraction(19999, 20000), 9999),
        (Fraction(5, 2), 25000),
    ],
)
def test_spec_and_hand_examples(value, expected):
    q = quantize_weighted_deficit(value)
    assert type(q) is int
    assert q == expected


def _grid():
    values = []
    for den in (1, 2, 3, 7, 9, 10000, 10001, 20000, 99991, 10**12 + 39):
        for num in (0, 1, 2, den - 1, den, den + 1, 3 * den + 2, 10**6 + 7):
            if num >= 0:
                values.append(Fraction(num, den))
    return values


@pytest.mark.parametrize("value", _grid())
def test_exact_rational_floor_boundary(value):
    q = quantize_weighted_deficit(value)
    scaled = SCALE * value
    assert Fraction(q) <= scaled
    assert scaled < Fraction(q + 1)


def test_no_float_rounding_for_large_numerators():
    # float(2**60 + 1) == 2**60, so a float path would return the wrong integer.
    assert quantize_weighted_deficit(Fraction(2**60 + 1, SCALE)) == 2**60 + 1


def test_no_float_rounding_just_below_an_integer():
    # 10000 * v = 1 - 10**-40; floor is 0, but float arithmetic would round up to 1.
    value = Fraction(10**40 - 1, 10**44)
    assert quantize_weighted_deficit(value) == 0


def test_floor_not_round_to_nearest():
    # 10000 * v = 0.9999...; nearest rounding would give 1.
    assert quantize_weighted_deficit(Fraction(9999, 10**8)) == 0
    assert quantize_weighted_deficit(Fraction(19999, 20000 * 10000)) == 0


def test_max_int64_output_accepted():
    assert quantize_weighted_deficit(Fraction(INT64_MAX, SCALE)) == INT64_MAX


def test_largest_value_below_overflow_accepted():
    value = Fraction(INT64_MAX + 1, SCALE) - Fraction(1, 10**30)
    assert quantize_weighted_deficit(value) == INT64_MAX


def test_next_output_value_raises_overflow():
    with pytest.raises(OverflowError):
        quantize_weighted_deficit(Fraction(INT64_MAX + 1, SCALE))


def test_huge_value_raises_overflow_not_clamped():
    with pytest.raises(OverflowError):
        quantize_weighted_deficit(Fraction(10**40))


@pytest.mark.parametrize(
    "bad",
    [0.5, 0.0, float("nan"), True, False, Decimal("0.5"), Decimal(1), 0, 1, 10001, "1/3", None],
)
def test_wrong_types_raise_type_error(bad):
    with pytest.raises(TypeError):
        quantize_weighted_deficit(bad)


@pytest.mark.parametrize("bad", [Fraction(-1, 3), Fraction(-1), Fraction(-1, 10**30)])
def test_negative_values_raise_value_error(bad):
    with pytest.raises(ValueError):
        quantize_weighted_deficit(bad)


def test_large_negative_value_is_value_error_not_overflow():
    with pytest.raises(ValueError):
        quantize_weighted_deficit(Fraction(-(10**40)))


def test_scale_is_not_a_caller_parameter():
    params = list(inspect.signature(quantize_weighted_deficit).parameters)
    assert params == ["value"]
    with pytest.raises(TypeError):
        quantize_weighted_deficit(Fraction(1, 3), 100)  # type: ignore[call-arg]


def test_input_unchanged_and_deterministic():
    value = Fraction(1, 3)
    before = (value.numerator, value.denominator)
    first = quantize_weighted_deficit(value)
    second = quantize_weighted_deficit(value)
    assert first == second == 3333
    assert (value.numerator, value.denominator) == before
