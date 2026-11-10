# covers: V1-A15
"""RETAIL_OPTIMIZED behavior beyond the oracle values, and the independent verifier's refusals."""

from datetime import date, timedelta

import pytest
from ortools.sat.python import cp_model

from app.schemas.v1_planning import TransferV3
from app.services.optimization.methods import run_method
from app.services.optimization.verify import verify_plan
from tests.optimization.test_retail_oracle import load


def scenario(name, **changes):
    s, _ = load(name)
    return s.model_copy(update=changes)


def test_usd_unavailable_when_any_included_product_lacks_price():
    s = scenario("retail-usd-flip")
    unpriced = s.products[1].model_copy(update={"unit_value_usd": None})
    s = s.model_copy(update={"products": (s.products[0], unpriced)})

    usd = run_method(s, "RETAIL_OPTIMIZED", "USD")
    units = run_method(s, "RETAIL_OPTIMIZED", "UNITS")

    assert (usd.verified, usd.failure_reason, usd.transfers) == (False, "USD_UNAVAILABLE", ())
    assert usd.usd_unavailable_reason == "USD unavailable: no unit value for Olive oil"
    assert units.verified and units.transfers  # units stay available
    assert units.usd_unavailable_reason == usd.usd_unavailable_reason


def test_default_weights_disclosed_in_result():
    result = run_method(scenario("retail-expiry-transfer"), "RETAIL_OPTIMIZED", "UNITS")
    assert result.retail_weights.model_dump() == {"w_exp": 1, "w_lost": 1}


def test_weights_editable():
    """lost-vs-waste: at w_exp = 3 accepting one expiry for two sales no longer pays (README)."""
    base = scenario("retail-lost-vs-waste")
    heavy = base.model_copy(
        update={"retail_weights": base.retail_weights.model_copy(update={"w_exp": 3})}
    )
    default = run_method(base, "RETAIL_OPTIMIZED", "UNITS")
    edited = run_method(heavy, "RETAIL_OPTIMIZED", "UNITS")
    assert [t.quantity for t in default.transfers] == [3]
    assert (edited.transfers, edited.objective) == ((), "2")
    assert edited.retail_weights.model_dump() == {"w_exp": 3, "w_lost": 1}


def test_bd51_relaxed_retail_selling_on_day_5_counts():
    """The Retail half of BD-51: day5-expiry moves 3 units that sell on days 3-5.

    The Pantry half (the same transfer rejected inside a 3-day window) lands with
    CR-w1-solver-1's planning_days in test_bd51_relaxed_retail_only.
    """
    result = run_method(scenario("retail-day5-expiry"), "RETAIL_OPTIMIZED", "UNITS")
    assert [t.quantity for t in result.transfers] == [3]
    report = verify_plan(scenario("retail-day5-expiry"), result.transfers)
    (lot,) = report.sublots
    assert lot.consumed == (0, 0, 1, 1, 1, 0, 0)


def test_single_dispatch_on_first_planning_day():
    s = scenario("retail-expiry-transfer")
    result = run_method(s, "RETAIL_OPTIMIZED", "UNITS")
    assert {t.ship_date for t in result.transfers} == {s.first_planning_date}
    late = result.transfers[0].model_copy(
        update={
            "ship_date": s.first_planning_date + timedelta(days=1),
            "arrival_date": result.transfers[0].arrival_date + timedelta(days=1),
        }
    )
    assert "SINGLE_DISPATCH_ON_FIRST_PLANNING_DAY" in verify_plan(s, (late,)).violations


@pytest.fixture
def native(monkeypatch):
    """Report a chosen native status for every solve, keeping CP-SAT's real solution."""

    def use(name):
        monkeypatch.setattr(cp_model.CpSolver, "status_name", lambda self, status=None: name)

    return use


def test_native_status_preserved(native):
    native("FEASIBLE")
    result = run_method(scenario("retail-expiry-transfer"), "RETAIL_OPTIMIZED", "UNITS")
    assert result.native_status == "FEASIBLE"  # never relabeled OPTIMAL
    assert result.verified and result.transfers
    (product,) = result.products
    assert (product.native_status, product.gap) == ("FEASIBLE", "0.000000")


def test_no_solution_is_reported_without_a_plan(native):
    native("UNKNOWN")
    result = run_method(scenario("retail-expiry-transfer"), "RETAIL_OPTIMIZED", "UNITS")
    assert (result.native_status, result.verified, result.transfers) == ("UNKNOWN", False, ())
    assert result.failure_reason == "NO_SOLUTION:P"
    assert result.products[0].native_status == "UNKNOWN"


def plan(s, *rows):
    return tuple(
        TransferV3(
            id=f"t{i}",
            product_id=p,
            from_location_id=a,
            to_location_id=b,
            quantity=q,
            ship_date=s.first_planning_date,
            arrival_date=s.first_planning_date + timedelta(days=d),
            batch_ids=batches,
        )
        for i, (p, a, b, q, d, batches) in enumerate(rows)
    )


@pytest.mark.parametrize(
    ("name", "rows", "violation"),
    [
        # a 7th a1 unit can't sell at B before its 11-04 expiry (README: y <= 6)
        (
            "retail-expiry-transfer",
            [("P", "A", "B", 7, 1, ("a1",))],
            "TRANSFER_NOT_CONSUMED_IN_WINDOW",
        ),
        # FEFO packing draws a1 before a2
        ("retail-lost-vs-waste", [("P", "A", "B", 3, 1, ("a2",))], "PACKING_FEFO_MISMATCH"),
        # A keeps 10 + 1 - 5 = 6 units for 7 days of its own sales
        ("retail-lost-vs-waste", [("P", "A", "B", 5, 1, ("a1", "a2"))], "DONOR_PROTECTION"),
        # 3 + 2 handling units on a route that carries 4 per batch
        (
            "retail-usd-flip",
            [("P", "D", "B", 3, 1, ("p1",)), ("Q", "D", "B", 2, 1, ("q1",))],
            "ROUTE_CAPACITY",
        ),
        # DCs never receive and the scenario has no B -> D route
        ("retail-usd-no-flip", [("Q", "B", "D", 1, 1, ("q1",))], "UNKNOWN_ROUTE_OR_PRODUCT"),
        # a1 expires before it could arrive on the 2-day route
        ("retail-nothing-to-move", [("P", "A", "B", 1, 2, ("a1",))], "PACKING_FEFO_MISMATCH"),
    ],
)
def test_verifier_rejects(name, rows, violation):
    s = scenario(name)
    report = verify_plan(s, plan(s, *rows))
    assert not report.passed
    assert violation in report.violations


def latest_expiry_first(expiry, available, ident):
    return (-(expiry or date.max).toordinal(), available, ident)


def highest_id_first(expiry, available, ident):
    return (expiry or date.max, available, [-ord(ch) for ch in ident])


@pytest.mark.parametrize(
    ("mutant", "a1_expiry"),
    [(latest_expiry_first, date(2026, 11, 3)), (highest_id_first, date(2026, 11, 30))],
)
def test_verifier_fefo_check_is_independent_of_the_shared_packing(monkeypatch, mutant, a1_expiry):
    """S1: lost-vs-waste A holds a1 (1 unit) and a2 (10, 11-30); both are eligible for the 1-day
    route. Sending 2 units of a2 while a1 stays at A breaks FEFO: a1 expires first (11-03), or
    on the same day with the lower batch id. With the shared FEFO order mutated the same way, the
    shared packing draws a2 too, so only an independent FEFO check can still refuse the plan."""
    from app.services.optimization import v3

    s = scenario("retail-lost-vs-waste")
    a1 = s.batches[0].model_copy(update={"expiry_date": a1_expiry})
    s = s.model_copy(update={"batches": (a1, *s.batches[1:])})
    monkeypatch.setattr(v3, "fefo_key", mutant)
    later_first = plan(s, ("P", "A", "B", 2, 1, ("a2",)))
    assert [x.splits for x in v3.pack(s, v3.quantities_of(later_first))] == [(("a2", 2),)]
    report = verify_plan(s, later_first)
    assert report.violations == ("PACKING_FEFO_MISMATCH",)
