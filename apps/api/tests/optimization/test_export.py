# covers: V1-A16
"""Plan export CSV: scenario identity, method, mode, why/effect text and the simulated-plan note."""

import csv
import io
from datetime import UTC, datetime
from uuid import UUID

import pytest

from app.schemas.v1_planning import InboundV3, SavedComparisonV3
from app.services.optimization.actions import decision_actions
from app.services.optimization.compare import compare_methods
from app.services.optimization.export import COLUMNS, SIMULATED_NOTE, export_plan_csv
from app.services.optimization.v3 import PER_PRODUCT_LABEL
from tests.optimization.test_retail_oracle import load

SCENARIO = UUID("00000000-0000-4000-8000-0000000000e1")
COMPARISON = UUID("00000000-0000-4000-8000-0000000000e2")
HASH = "b" * 64


def saved(s, measure="UNITS"):
    result = compare_methods(
        s,
        ("NO_TRANSFERS", "SOONEST_EXPIRY_FIRST", "RETAIL_OPTIMIZED"),
        measure,
        scenario_id=SCENARIO,
        scenario_hash=HASH,
    )
    return SavedComparisonV3(
        id=COMPARISON,
        network_id=s.network_id,
        scenario_id=SCENARIO,
        recorded_at=datetime(2026, 11, 7, tzinfo=UTC),
        result=result,
        assumptions=s.assumptions,
        inbound_file_provided=s.inbound_file_provided,
    )


def rows(text):
    return list(csv.DictReader(io.StringIO(text)))


def test_export_columns():
    s, _ = load("retail-expiry-transfer")
    comparison = saved(s, "USD")
    method = comparison.result.methods[2]
    (action,) = decision_actions(s, method, comparison_id=COMPARISON).actions
    text = export_plan_csv(comparison, "RETAIL_OPTIMIZED", [action.id], scenario=s)
    assert (
        next(csv.reader(io.StringIO(text)))
        == list(COLUMNS)
        == [
            "scenario_id",
            "scenario_hash",
            "method",
            "network_mode",
            "product",
            "unit",
            "quantity",
            "from",
            "to",
            "ship_date",
            "arrival_date",
            "why",
            "effect",
            "note",
        ]
    )
    (row,) = rows(text)
    assert row == {
        "scenario_id": str(SCENARIO),
        "scenario_hash": HASH,
        "method": "RETAIL_OPTIMIZED",
        "network_mode": "RETAIL",
        "product": "Yogurt",
        "unit": "case",
        "quantity": "6",
        "from": "Store A",
        "to": "Store B",
        "ship_date": "2026-11-02",
        "arrival_date": "2026-11-03",
        "why": action.why_text,
        "effect": (
            "sender unmet +0 cases; receiver unmet -6 cases; expired -6 cases; USD -30.00 "
            "(effect of this action given the rest of the plan; effects don't add up across "
            "actions)"
        ),
        "note": "simulated plan; no stock was reserved or moved; no scheduled deliveries provided; "
        "optimized per product, with shared capacity split in advance; product solved OPTIMAL",
    }
    assert SIMULATED_NOTE == "simulated plan; no stock was reserved or moved"


def test_export_only_selected_actions():
    s, _ = load("retail-usd-no-flip")
    comparison = saved(s)
    actions = decision_actions(s, comparison.result.methods[2], comparison_id=COMPARISON).actions
    chosen = [a.id for a in actions if a.effect.product_id == "Q"]
    exported = rows(export_plan_csv(comparison, "RETAIL_OPTIMIZED", chosen, scenario=s))
    assert [(r["product"], r["quantity"]) for r in exported] == [("Olive oil", "10")]
    with pytest.raises(KeyError):
        export_plan_csv(comparison, "RETAIL_OPTIMIZED", ["t-not-in-plan"], scenario=s)


def test_no_scheduled_deliveries_note_when_no_inbound():
    s, _ = load("retail-usd-no-flip")
    arriving = InboundV3(
        id="in1",
        location_id="B",
        product_id="P",
        quantity=1,
        arrival_date=s.first_planning_date,
        expiry_date=None,
        non_expiring=True,
    )
    with_file = s.model_copy(update={"inbound": (arriving,), "inbound_file_provided": True})
    for scenario, note in (
        (s, SIMULATED_NOTE + "; no scheduled deliveries provided"),
        (with_file, SIMULATED_NOTE),
    ):
        comparison = saved(scenario)
        ids = [t.id for t in comparison.result.methods[2].transfers]
        exported = rows(export_plan_csv(comparison, "RETAIL_OPTIMIZED", ids, scenario=scenario))
        solved = f"; {PER_PRODUCT_LABEL}; product solved OPTIMAL"
        assert exported and {r["note"] for r in exported} == {note + solved}


def test_capacity_note_when_capacity_was_not_provided():  # CR-w1-web-6
    s, _ = load("retail-usd-no-flip")
    blank = "Receiving capacity at B: capacity not provided — no limit assumed"  # data lane wording
    assumed = s.model_copy(update={"assumptions": (*s.assumptions, blank)})
    no_inbound = "; no scheduled deliveries provided"
    capacity = "; capacity not provided — no limit assumed"
    for scenario, note in ((s, no_inbound), (assumed, capacity + no_inbound)):
        comparison = saved(scenario)
        ids = [t.id for t in comparison.result.methods[2].transfers]
        exported = rows(export_plan_csv(comparison, "RETAIL_OPTIMIZED", ids, scenario=scenario))
        solved = f"; {PER_PRODUCT_LABEL}; product solved OPTIMAL"
        assert exported and {r["note"] for r in exported} == {SIMULATED_NOTE + note + solved}


def test_export_rejects_unverified_method():
    s, _ = load("retail-expiry-transfer")
    comparison = saved(s)
    method = comparison.result.methods[2]
    broken = comparison.model_copy(
        update={
            "result": comparison.result.model_copy(
                update={
                    "methods": (
                        *comparison.result.methods[:2],
                        method.model_copy(update={"verified": False, "transfers": ()}),
                    )
                }
            )
        }
    )
    with pytest.raises(ValueError, match="RESULT_NOT_VERIFIED"):
        export_plan_csv(broken, "RETAIL_OPTIMIZED", ["x"], scenario=s)


def test_export_rejects_scenario_of_another_comparison():
    s, _ = load("retail-expiry-transfer")
    other, _ = load("retail-usd-no-flip")
    comparison = saved(s)
    other = other.model_copy(update={"network_id": UUID("00000000-0000-4000-8000-0000000000ff")})
    with pytest.raises(ValueError, match="SCENARIO_MISMATCH"):
        export_plan_csv(comparison, "RETAIL_OPTIMIZED", [], scenario=other)


def test_export_pantry_plan():
    s, _ = load("pantry-four-methods")
    methods = ("NO_TRANSFERS", "MOST_URGENT_FIRST", "EGP_PI_INSPIRED")
    result = compare_methods(s, methods, "UNITS", scenario_id=SCENARIO, scenario_hash=HASH)
    comparison = SavedComparisonV3(
        id=COMPARISON,
        network_id=s.network_id,
        scenario_id=SCENARIO,
        recorded_at=datetime(2026, 11, 7, tzinfo=UTC),
        result=result,
        assumptions=s.assumptions,
        inbound_file_provided=s.inbound_file_provided,
    )
    ids = [t.id for t in result.methods[1].transfers]
    exported = rows(export_plan_csv(comparison, "MOST_URGENT_FIRST", ids, scenario=s))
    assert [(r["to"], r["quantity"], r["unit"]) for r in exported] == [
        ("Pantry 2", "3", "case"),
        ("Pantry 3", "1", "case"),
    ]  # README: MOST_URGENT_FIRST P2 3, P3 1
    assert {(r["network_mode"], r["method"], r["note"]) for r in exported} == {
        ("PANTRY", "MOST_URGENT_FIRST", SIMULATED_NOTE + "; no scheduled deliveries provided")
    }
    assert all("over 2 days" in r["why"] and "USD" not in r["effect"] for r in exported)


def test_export_says_optimized_per_product_and_names_each_solved_product():
    """W0-optimizer-decomposition 4: plan exports carry the per-product wording and say which
    products were solved; heuristic rows don't claim optimization."""
    s, _ = load("retail-usd-flip")
    comparison = saved(s)
    for method, claimed in (("RETAIL_OPTIMIZED", True), ("SOONEST_EXPIRY_FIRST", False)):
        chosen = next(m for m in comparison.result.methods if m.method == method)
        exported = rows(
            export_plan_csv(comparison, method, [t.id for t in chosen.transfers], scenario=s)
        )
        assert exported
        status = {p.product_id: p.native_status for p in chosen.products}
        names = {p.id: p.name for p in s.products}
        for row in exported:
            pid = next(k for k, v in names.items() if v == row["product"])
            assert (PER_PRODUCT_LABEL in row["note"]) is claimed
            assert (f"product solved {status[pid]}" in row["note"]) is claimed


def test_export_neutralizes_spreadsheet_formulas():
    """Names come from the user's CSV import; a cell starting with = + - @ is never a formula."""
    s, _ = load("retail-usd-flip")
    hostile = s.model_copy(
        update={
            "products": tuple(p.model_copy(update={"name": "=HYPERLINK(1)"}) for p in s.products),
            "locations": tuple(
                loc.model_copy(update={"name": f"@{loc.name}"}) for loc in s.locations
            ),
        }
    )
    comparison = saved(hostile)
    optimized = comparison.result.methods[2]
    text = export_plan_csv(
        comparison, "RETAIL_OPTIMIZED", [t.id for t in optimized.transfers], scenario=hostile
    )
    for row in rows(text):
        for column in ("product", "from", "to", "why"):
            assert row[column][0] == "'", (column, row[column])
