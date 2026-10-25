"""OR-DEC-019 [PROVISIONAL]: independent pre-solver mathematical evidence."""

import ast
import json
from fractions import Fraction
from pathlib import Path

import pytest

from scripts.or_enumerate import (
    compile_coefficients,
    deficit,
    enumerate_fixture,
    flags,
    oracle_daily,
    oracle_pack,
    product_profile,
)


def test_oracle_has_no_application_or_native_solver_dependency():
    # OR-DEC-019 [PROVISIONAL]: behavioral coverage in decision-manifest.json.
    source = Path(__file__).parents[2] / "scripts/or_enumerate.py"
    tree = ast.parse(source.read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            assert all(not item.name.startswith(("app", "ortools")) for item in node.names)
        if isinstance(node, ast.ImportFrom):
            assert not (node.module or "").startswith(("app", "ortools"))


@pytest.mark.parametrize(
    ("fixture", "expected"),
    [
        ("ap-ablation-v1", [((1, 0), Fraction(19, 8)), ((0, 1), Fraction(2))]),
        ("rp-ablation-v1", [((0, 1), Fraction(11, 4)), ((1, 0), Fraction(21, 8))]),
    ],
)
def test_decision_changing_ablations(fixture, expected):
    result = enumerate_fixture(fixture)
    for row, (vector, objective) in zip(result["results"], expected, strict=True):
        assert row["optimum_count"] == 1
        assert tuple(row["optima"][0][0]) == vector
        assert Fraction(**row["objective"]) == objective
        assert row["purpose"] == ("PRIMARY" if row["configuration"] == "full" else "ABLATION")


def test_six_beneficiary_unique_optima():
    result = enumerate_fixture("six-beneficiary-v1")
    assert result["vectors_per_product"] == 435
    assert result["feasible_pairs"] == 435**2
    classical, research = result["results"]
    for row, vector, objective in (
        (classical, [1, 1, 1, 1, 1, 1], Fraction(163, 50)),
        (research, [2, 2, 1, 1, 0, 0], Fraction(1393, 300)),
    ):
        assert row["optimum_count"] == 1
        assert row["optima"] == [[vector, vector]]
        assert Fraction(**row["objective"]) == objective


def test_exact_floor_equality_and_zero_boundaries():
    # OR-DEC-006/007/018 [PROVISIONAL]: quantized strict flags and group limits.
    assert deficit(1, 3, Fraction(1)) == 3333
    assert deficit(1, 20_000, Fraction(1)) == 0
    assert deficit(10_001, 10_000, Fraction(1)) == 10_001
    assert deficit(0, 0, Fraction(2)) == 0
    assert flags((7500, 7501))[0] == (False, True)
    assert flags((5000, 0))[1] == (False, False)
    assert flags((5001, 0))[1] == (True, False)
    assert flags(()) == ((), ())
    with pytest.raises(ValueError, match="singleton"):
        flags((1,))


def test_rp_uses_current_candidate_mean():
    assert flags((9000, 9000))[1] == (False, False)
    assert flags((9000, 0))[1] == (True, False)
    assert flags((0, 9000))[1] == (False, True)


def test_zero_targets_do_not_enter_group_denominators():
    result = product_profile((0, 2, 2), (0, 1, 0), (Fraction(2),) * 3)
    assert result["n"] == 2
    assert result["q"] == (10_000, 20_000)
    with pytest.raises(ValueError, match="singleton"):
        product_profile((0, 2), (0, 0), (Fraction(1),) * 2)


def test_integer_coefficient_compiler_preserves_objective_and_rejects_overflow():
    # OR-DEC-018 [PROVISIONAL]: behavioral coverage in decision-manifest.json.
    terms = (Fraction(1, 2), Fraction(1, 6), Fraction(1, 100))
    coefficients, scale = compile_coefficients(terms, (20_000, 120_000, 10_000))
    assert coefficients == (150, 50, 3)
    assert scale == 300
    values = (123, 99, 5000)
    exact = sum((c * v for c, v in zip(terms, values, strict=True)), Fraction())
    integer = sum(c * v for c, v in zip(coefficients, values, strict=True))
    assert Fraction(integer, scale) == exact
    with pytest.raises(ValueError, match="NUMERIC_RANGE_UNSUPPORTED"):
        compile_coefficients((Fraction(1),), (2**60,))


def test_hand_lost_sales_expiry_and_arrival():
    # OR-DEC-001/004 [PROVISIONAL]: an arrival cannot repair prior lost demand.
    assert oracle_daily((50, 40), ((40, 0, 8, "a"),)) == ((40, 10, 0, 0), (0, 40, 0, 0))
    assert oracle_daily((5, 5), ((5, 1, 8, "a"),)) == ((0, 5, 0, 0), (5, 0, 0, 0))
    assert oracle_daily((2, 2), ((3, 0, 1, "a"), (3, 0, 8, "b"))) == ((2, 0, 0, 4), (2, 0, 1, 1))


def test_loading_fefo_skips_expiry_exception_and_never_reuses_source():
    # Longer route first; early lot cannot survive it and is available on short route.
    lots = ((2, 1, "early"), (2, 8, "late"))
    packed, residual = oracle_pack(lots, (("short", 0, 2), ("long", 2, 2)))
    assert packed == (("late", "long", 2), ("early", "short", 2))
    assert residual == (0, 0)
    with pytest.raises(ValueError, match="insufficient"):
        oracle_pack(lots, (("long", 2, 3),))


def test_loading_exhaustively_matches_closed_form_min_and_conservation():
    for stock_a in range(4):
        for stock_b in range(4):
            for send_a in range(stock_a + stock_b + 1):
                for send_b in range(stock_a + stock_b - send_a + 1):
                    allocations, balances = oracle_pack(
                        ((stock_a, 8, "a"), (stock_b, 8, "b")),
                        (("route_a", 0, send_a), ("route_b", 0, send_b)),
                    )
                    actual = {(lot, route): qty for lot, route, qty in allocations}
                    first = min(stock_a, send_a)
                    assert actual.get(("a", "route_a"), 0) == first
                    assert actual.get(("b", "route_a"), 0) == send_a - first
                    second = min(stock_a - first, send_b)
                    assert actual.get(("a", "route_b"), 0) == second
                    assert actual.get(("b", "route_b"), 0) == send_b - second
                    assert sum(balances) + sum(x[2] for x in allocations) == stock_a + stock_b


def test_cli_emits_exact_reproducible_json(tmp_path):
    import subprocess
    import sys

    target = tmp_path / "oracle.json"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "scripts.or_enumerate",
            "--fixture",
            "ap-ablation-v1",
            "--output",
            str(target),
        ],
        cwd=Path(__file__).resolve().parents[2],
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    output = json.loads(target.read_text())
    assert output["source_kind"] == "SIMULATED"
    assert len(output["fingerprint"]) == 64
    assert output["decision_ids"]
