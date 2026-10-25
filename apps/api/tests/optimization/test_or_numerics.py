"""Audit the domains actually emitted by the pinned OR-Tools API."""

import pytest
from ortools.sat.python import cp_model

from app.services.optimization.numerics import LIMIT, NumericRangeUnsupported, audit_model


def test_audit_reads_actual_upper_domain_from_native_repeated_container():
    # OR-DEC-018 [PROVISIONAL]: pinned native containers mishandle negative indexes.
    model = cp_model.CpModel()
    model.new_int_var(0, 20000, "weighted_deficit")
    report = audit_model(model)
    assert report["maximum_activity"] == 20000


def test_audit_rejects_unsafe_linear_activity_before_solving():
    model = cp_model.CpModel()
    value = model.new_int_var(0, LIMIT // 2, "large_domain")
    model.add(2 * value >= 0)
    with pytest.raises(NumericRangeUnsupported, match="NUMERIC_RANGE_UNSUPPORTED"):
        audit_model(model)


def test_audit_rejects_unsafe_objective_activity_before_solving():
    model = cp_model.CpModel()
    value = model.new_int_var(0, LIMIT // 2, "large_domain")
    model.minimize(2 * value)
    with pytest.raises(NumericRangeUnsupported, match="NUMERIC_RANGE_UNSUPPORTED"):
        audit_model(model)
