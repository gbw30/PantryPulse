"""Exact fixed-point floor primitive (BACKEND-SPEC.md section 13.4, BE-04).

Encodes an already computed nonnegative weighted deficit at the fixed scale 10000. It does
not compute policy weights, AP/RP flags or an objective, and its output check does not prove
that later coefficient products or sums fit int64 (OPEN-23/24 and the research gate).
"""

from fractions import Fraction

SCALE = 10000
INT64_MAX = 9223372036854775807


def quantize_weighted_deficit(value: Fraction) -> int:
    """Return floor(10000 * value) using integer arithmetic only.

    Raises TypeError unless value is a Fraction, ValueError if it is negative and
    OverflowError if the result exceeds int64. Never clamps or rounds to nearest.
    """
    if not isinstance(value, Fraction):
        raise TypeError(f"value must be a fractions.Fraction, got {type(value).__name__}")
    if value < 0:
        raise ValueError("value must be nonnegative")
    # Fraction keeps a positive denominator, so // is the exact mathematical floor.
    q = (SCALE * value.numerator) // value.denominator
    if q > INT64_MAX:
        raise OverflowError(f"quantized value {q} exceeds int64 maximum {INT64_MAX}")
    return q
