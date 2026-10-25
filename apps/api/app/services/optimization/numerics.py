"""Exact coefficient compilation and intervals of every emitted native expression."""

from dataclasses import dataclass
from fractions import Fraction
from functools import reduce
from math import gcd, lcm

LIMIT = 2**60


class NumericRangeUnsupported(ValueError):
    pass


@dataclass(frozen=True)
class ObjectiveHandles:
    terms: tuple
    coefficients: tuple[int, ...]
    scale: Fraction
    auxiliaries: dict


def compile_objective(model, terms, auxiliaries) -> ObjectiveHandles:
    # OR-DEC-018 [PROVISIONAL]: exact LCM/GCD; no floating objective or pre-objective.
    terms = [(v, Fraction(c)) for v, c in terms if c]
    denominator = lcm(*(c.denominator for _, c in terms)) if terms else 1
    integers = [int(c * denominator) for _, c in terms]
    common = reduce(gcd, integers, 0) or 1
    coefficients = tuple(c // common for c in integers)
    variables = tuple(v for v, _ in terms)
    model.minimize(sum(c * v for c, v in zip(coefficients, variables, strict=True)))
    return ObjectiveHandles(variables, coefficients, Fraction(common, denominator), auxiliaries)


def audit_model(model) -> dict:
    """Read domains/coefficients actually emitted, including reified/min/max constraints."""
    # OR-DEC-018 [PROVISIONAL]: interval magnitude must be strictly below 2**60.
    proto = model.proto
    # OR-Tools 9.15's native repeated container does not implement Python negative
    # indexing correctly. Read the final endpoint through its nonnegative index.
    domains = [(int(v.domain[0]), int(v.domain[len(v.domain) - 1])) for v in proto.variables]
    records = []

    def check(label, indices, coefficients, offset=0):
        low = high = int(offset)
        for index, coefficient in zip(indices, coefficients, strict=True):
            index, coefficient = int(index), int(coefficient)
            lo, hi = domains[index]
            low += min(coefficient * lo, coefficient * hi)
            high += max(coefficient * lo, coefficient * hi)
        if max(abs(low), abs(high)) >= LIMIT:
            raise NumericRangeUnsupported(f"NUMERIC_RANGE_UNSUPPORTED:{label}")
        records.append({"expression": label, "lower": low, "upper": high})

    for i, (low, high) in enumerate(domains):
        check(f"domain:{i}", (), (), low)
        check(f"domain-upper:{i}", (), (), high)
    for i, constraint in enumerate(proto.constraints):
        if constraint.has_linear():
            check(f"linear:{i}", constraint.linear.vars, constraint.linear.coeffs)
        elif constraint.has_lin_max():
            expressions = [constraint.lin_max.target, *constraint.lin_max.exprs]
            for j, expression in enumerate(expressions):
                check(f"max:{i}:{j}", expression.vars, expression.coeffs, expression.offset)
        elif constraint.has_bool_or() or constraint.has_bool_and():
            pass  # literal activities are in {0,1}; their indexes are native-validated below
        else:
            raise NumericRangeUnsupported(f"UNAUDITED_CONSTRAINT:{i}")
        for literal in constraint.enforcement_literal:
            index = int(literal) if literal >= 0 else -int(literal) - 1
            if not 0 <= domains[index][0] <= domains[index][1] <= 1:
                raise NumericRangeUnsupported("INVALID_ENFORCEMENT_LITERAL")
    if proto.has_floating_point_objective():
        raise NumericRangeUnsupported("FLOATING_OBJECTIVE_FORBIDDEN")
    if proto.has_objective():
        check(
            "objective", proto.objective.vars, proto.objective.coeffs, int(proto.objective.offset)
        )
    validation = model.validate()
    if validation:
        raise ValueError(f"MODEL_INVALID:{validation}")
    return {
        "limit_exclusive": LIMIT,
        "expressions": records,
        "maximum_activity": max(
            (max(abs(r["lower"]), abs(r["upper"])) for r in records), default=0
        ),
    }
