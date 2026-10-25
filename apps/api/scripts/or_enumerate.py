"""Independent standard-library OR oracle. No application or native solver imports.

Run: python -m scripts.or_enumerate --fixture six-beneficiary-v1 --output PATH.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from fractions import Fraction
from itertools import product
from math import gcd, lcm
from pathlib import Path

SCALE = 10_000
LIMIT = 2**60
DECISIONS = tuple(f"OR-DEC-{i:03d}" for i in (1, 4, 6, 7, 8, 17, 18, 19))


def deficit(unmet: int, target: int, weight: Fraction) -> int:
    """OR-DEC-018 [PROVISIONAL]: computational floor of exact rational operands."""
    if type(unmet) is not int or type(target) is not int or min(unmet, target) < 0:
        raise ValueError("invalid nonnegative integer deficit input")
    if target == 0:
        if unmet:
            raise ValueError("nonzero unmet for zero target")
        return 0
    exact = SCALE * weight * unmet / target
    return exact.numerator // exact.denominator


def flags(q: tuple[int, ...], ap: int = 7500, rp: int = 2500):
    """OR-DEC-006/007 [PROVISIONAL]: strict candidate-dependent indicators."""
    if len(q) == 1:
        raise ValueError("unsupported singleton RP group")
    n = len(q)
    return tuple(x > ap for x in q), tuple(n * x - sum(q) > n * rp for x in q)


def product_profile(targets, served, weights):
    if not len(targets) == len(served) == len(weights):
        raise ValueError("goal dimension mismatch")
    if any(type(f) is not int or f < 0 or f > r for f, r in zip(served, targets, strict=True)):
        raise ValueError("invalid service")
    q = tuple(
        deficit(r - f, r, v)
        for r, f, v in zip(targets, served, weights, strict=True)
        if r > 0
    )
    ap, rp = flags(q)
    n = len(q)
    return {
        "q": q, "n": n, "W": sum(q), "Z": max(q, default=0), "ap": ap, "rp": rp,
        "AP": Fraction(max(0, SCALE * sum(ap) - 2500 * n), SCALE * n) if n else Fraction(),
        "RP": Fraction(max(0, SCALE * sum(rp) - 2500 * n), SCALE * n) if n else Fraction(),
    }


def compile_coefficients(coefficients, domains):
    """Independent LCM/GCD reference and full worst-case objective activity."""
    if len(coefficients) != len(domains):
        raise ValueError("coefficient/domain mismatch")
    denominator = lcm(*(coefficient.denominator for coefficient in coefficients))
    integers = tuple(int(coefficient * denominator) for coefficient in coefficients)
    divisor = gcd(*integers) or 1
    integers = tuple(x // divisor for x in integers)
    scale = Fraction(denominator, divisor)
    if sum(abs(c) * d for c, d in zip(integers, domains, strict=True)) >= LIMIT:
        raise ValueError("NUMERIC_RANGE_UNSUPPORTED")
    return integers, scale


def oracle_pack(lots, routes):
    """Tiny test oracle: lots=(units,expiry,id), routes=(id,ETA,load); offsets zero based."""
    remaining = [lot[0] for lot in lots]
    packed = []
    # OR-DEC-004 [PROVISIONAL]: fixed route order; compatible-lot FEFO.
    for route, eta, requested in sorted(routes, key=lambda row: (-row[1], row[0])):
        for index in sorted(range(len(lots)), key=lambda i: (lots[i][1], lots[i][2])):
            if lots[index][1] <= eta:
                continue
            quantity = min(requested, remaining[index])
            if quantity:
                packed.append((lots[index][2], route, quantity))
                remaining[index] -= quantity
                requested -= quantity
        if requested:
            raise ValueError("insufficient compatible original stock")
    return tuple(packed), tuple(remaining)


def oracle_daily(demand, lots):
    """Tiny test oracle: lots=(units,available,expiry,id); served/unmet/expiry/end rows.

    Not an authoritative application recurrence. Expiry day D is unusable on D.
    """
    stock = {lot[3]: lot[0] for lot in lots}
    rows = []
    for day, target in enumerate(demand):
        expired = sum(
            stock[lid] for _, available, expiry, lid in lots if available <= day >= expiry
        )
        for _, available, expiry, lid in lots:
            if available <= day >= expiry:
                stock[lid] = 0
        shortage = target
        for _, available, expiry, lid in sorted(lots, key=lambda lot: (lot[2], lot[1], lot[3])):
            if available <= day < expiry:
                used = min(stock[lid], shortage)
                stock[lid] -= used
                shortage -= used
        ending = sum(stock[lid] for _, available, _, lid in lots if available <= day)
        rows.append((target - shortage, shortage, expired, ending))
    return tuple(rows)


def _fraction(value):
    return {"numerator": value.numerator, "denominator": value.denominator}


def _best(vectors, score):
    best, optima = None, []
    for vector in vectors:
        value = score(vector)
        if best is None or value < best:
            best, optima = value, [vector]
        elif value == best:
            optima.append(vector)
    return {"objective": _fraction(best), "optimum_count": len(optima), "optima": optima}


def _ablation(name):
    if name == "ap-ablation-v1":
        targets, weights, removed = (2, 3), (Fraction(3, 2),) * 2, "AP"
    else:
        targets, weights, removed = (2, 2), (Fraction(3, 2), Fraction(2)), "RP"
    vectors = tuple(v for v in product(*(range(r + 1) for r in targets)) if sum(v) <= 1)
    results = []
    for drop in (None, removed):
        def score(vector, drop=drop):
            profile = product_profile(targets, vector, weights)
            return (
                Fraction(profile["W"] + profile["Z"], 2 * SCALE)
                + (profile["AP"] if drop != "AP" else 0)
                + (profile["RP"] if drop != "RP" else 0)
            )
        row = _best(vectors, score)
        row["optima"] = [[list(v)] for v in row["optima"]]
        row.update({
            "configuration": "full" if drop is None else f"{drop}_disabled",
            "purpose": "PRIMARY" if drop is None else "ABLATION", "method": "EGP_PI_INSPIRED",
        })
        results.append(row)
    return {
        "targets": [targets], "weights": [[str(v) for v in weights]], "supply": [1],
        "vectors_per_product": len(vectors), "results": results,
        "physical_scope": "one hub, two beneficiaries, one positive demand day, expiry day 8",
    }


def _six():
    targets = (2,) * 6
    vulnerability = tuple(Fraction(10 - i, 5) for i in range(6))
    vectors = tuple(v for v in product(range(3), repeat=6) if sum(v) <= 6)
    rows = []
    feasible_pairs = sum(2 * sum(a) + sum(b) <= 18 for a in vectors for b in vectors)
    for method in ("CLASSICAL_GP", "EGP_PI_INSPIRED"):
        weights = (Fraction(1),) * 6 if method == "CLASSICAL_GP" else vulnerability
        profiles = {v: product_profile(targets, v, weights) for v in vectors}
        scale = 1_200_000
        best, winners = None, []
        for first in vectors:
            a = profiles[first]
            for second in vectors:
                if 2 * sum(first) + sum(second) > 18:
                    continue
                b = profiles[second]
                score = 60 * (a["W"] + b["W"] + max(a["Z"], b["Z"]))
                if method == "EGP_PI_INSPIRED":
                    score += int((a["AP"] + b["AP"] + a["RP"] + b["RP"]) * (scale // 2))
                cost_q = (SCALE * (sum(first) + sum(second))) // 12
                # 6,000,000 clears the cost floor's exact 1,000,000 denominator too.
                score = 5 * score + 6 * cost_q
                if best is None or score < best:
                    best, winners = score, [[list(first), list(second)]]
                elif score == best:
                    winners.append([list(first), list(second)])
        rows.append({
            "method": method, "purpose": "PRIMARY", "configuration": "full",
            "objective": _fraction(Fraction(best, scale * 5)),
            "optimum_count": len(winners), "optima": winners,
        })
    return {
        "targets": [list(targets), list(targets)], "weights": [[str(v) for v in vulnerability]] * 2,
        "supply": [6, 6], "handling": [2, 1], "global_handling": 18,
        "cost_reference": 12, "waste_reference": [6, 6],
        "vectors_per_product": len(vectors), "feasible_pairs": feasible_pairs,
        "results": rows,
        "physical_scope": (
            "one hub, six beneficiaries, two products, seven dates; H=3; ETA=0; expiry day 8"
        ),
    }


def enumerate_fixture(name):
    """Complete tiny math feasible sets; never native solver/runtime evidence."""
    if name == "six-beneficiary-v1":
        result = _six()
    elif name in {"ap-ablation-v1", "rp-ablation-v1"}:
        result = _ablation(name)
    else:
        raise ValueError("unknown independent oracle fixture")
    result.update({
        "schema_version": "or-oracle-v1", "fixture": name, "source_kind": "SIMULATED",
        "policy_version": "or-policy-v1", "decision_ids": list(DECISIONS),
        "evidence_kind": "INDEPENDENT_ENUMERATION_NOT_NATIVE_SOLVE",
    })
    payload = json.dumps(result, sort_keys=True, separators=(",", ":"))
    result["fingerprint"] = hashlib.sha256(payload.encode()).hexdigest()
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", required=True, choices=(
        "six-beneficiary-v1", "ap-ablation-v1", "rp-ablation-v1",
    ))
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        result = enumerate_fixture(args.fixture)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    except (OSError, ValueError) as error:
        parser.exit(2, f"oracle input/output error: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
