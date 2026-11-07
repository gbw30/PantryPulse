"""W1-S05 scale benchmark: a synthetic 100 × 500 or-input-v3 network, one full comparison per mode.

Run from apps/api (uses its locked environment):

    taskset -c 0-5 uv run --frozen python ../../scripts/or/bench_v1.py \
        --locations 100 --products 500 --mode retail [--out PATH]

Writes wall time, native status counts, verifier and union-check results and peak RSS per mode
to docs/optimization/evidence/v1-scale.json (merged by mode). The network is fictional and
generated from a fixed seed, shaped like spike S1 (docs/plans/v1/spikes/S1-optimizer.md):
4 hubs/DCs and 96 pantries/stores in a 300 × 300-mile square, each receiver reached from its
10 nearest senders, product classes AMPLE 60% / SHORT 25% / EXPIRY 15%, handling 1-3 units.
"""

import argparse
import json
import math
import os
import platform
import random
import resource
import subprocess
import sys
import time
from collections import Counter
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps/api"))

from app.schemas.v1_planning import ORInputV3  # noqa: E402

SEED = 20261104
SNAPSHOT = date(2026, 11, 1)
EVIDENCE = ROOT / "docs/optimization/evidence/v1-scale.json"
METHODS = {
    "retail": ("NO_TRANSFERS", "SOONEST_EXPIRY_FIRST", "RETAIL_OPTIMIZED"),
    "pantry": (
        "NO_TRANSFERS",
        "EQUAL_SHARE",
        "MOST_URGENT_FIRST",
        "CLASSICAL_GP",
        "EGP_PI_INSPIRED",
    ),
}


def generate(locations: int, products: int, mode: str, seed: int = SEED) -> ORInputV3:
    rng = random.Random(seed)
    hub, receiver = ("distribution_center", "store") if mode == "retail" else ("hub", "pantry")
    hubs = max(1, locations // 25)
    locs = [
        {
            "id": f"{'H' if i < hubs else 'R'}{i:03d}",
            "name": f"{'Hub' if i < hubs else 'Site'} {i}",
            "role": hub if i < hubs else receiver,
            "xy": (rng.uniform(0, 300), rng.uniform(0, 300)),
        }
        for i in range(locations)
    ]
    first = SNAPSHOT + timedelta(days=1)
    routes = []
    for r in locs[hubs:]:
        others = sorted(
            (o for o in locs if o is not r),
            key=lambda o: (math.dist(o["xy"], r["xy"]), o["id"]),
        )[:10]
        for o in others:
            miles = math.dist(o["xy"], r["xy"]) * 1.3
            routes.append(
                {
                    "from_location_id": o["id"],
                    "to_location_id": r["id"],
                    "travel_days": max(1, math.ceil(miles / 45 / 24)),  # W1-D07 formula
                    "method": "straight_line_estimate",
                    "road_miles": f"{miles:.1f}",
                    "cost_per_handling_unit_usd": None,
                    "capacity_per_batch": 300,
                }
            )
    prods, batches, demand = [], [], []
    for p in range(products):
        pid = f"P{p:03d}"
        kind = rng.choices(("AMPLE", "SHORT", "EXPIRY"), (60, 25, 15))[0]
        prods.append(
            {
                "id": pid,
                "name": f"Product {p}",
                "unit": rng.choice(("case", "bottle", "bag", "box")),
                "handling_units_per_unit": rng.randint(1, 3),
                "unit_value_usd": f"{rng.randint(100, 2000) / 100:.2f}",
            }
        )
        for loc in locs:
            lid = loc["id"]
            if loc["role"] == hub:
                for b in range(rng.randint(2, 3)):
                    expiry = first + timedelta(days=rng.randint(8, 45))
                    batches.append(
                        _batch(f"{pid}-{lid}-{b}", lid, pid, rng.randint(50, 200), expiry)
                    )
                continue
            rate = rng.randint(0, 6) if rng.random() < 0.9 else 0
            targets = [max(0, rate + rng.randint(-1, 1)) if rate else 0 for _ in range(7)]
            demand.append(
                {
                    "location_id": lid,
                    "product_id": pid,
                    "basis": "sales" if mode == "retail" else "demand",
                    "actual_provider": "seasonal_naive",
                    "fallback_reason": None,
                    "central_literals": [str(t) for t in targets],
                    "targets": targets,
                }
            )
            week = sum(targets)
            if kind == "AMPLE":
                stock, expiry = (
                    week + rng.randint(5, 20),
                    first + timedelta(days=rng.randint(10, 40)),
                )
            elif kind == "SHORT":
                stock = rng.randint(0, week) if rng.random() < 0.5 else week + rng.randint(5, 15)
                expiry = first + timedelta(days=rng.randint(8, 40))
            else:
                stock, expiry = week + rng.randint(5, 25), first + timedelta(days=rng.randint(1, 5))
            if stock:
                batches.append(_batch(f"{pid}-{lid}-0", lid, pid, stock, expiry))
                if rng.random() < 0.4:
                    batches.append(_batch(f"{pid}-{lid}-1", lid, pid, rng.randint(1, 10), None))
    payload = {
        "schema_version": "or-input-v3",
        "network_id": "00000000-0000-4000-8000-00000000b001",
        "organization_id": "00000000-0000-4000-8000-00000000b002",
        "dataset_version_id": "00000000-0000-4000-8000-00000000b003",
        "forecast_run_id": "00000000-0000-4000-8000-00000000b004",
        "mode": mode.upper(),
        "transfer_mode": "HUB_AND_PANTRY",
        "timezone": "America/New_York",
        "snapshot_as_of": SNAPSHOT.isoformat(),
        "first_planning_date": first.isoformat(),
        "horizon_days": 7,
        "locations": [{k: v for k, v in loc.items() if k != "xy"} for loc in locs],
        "products": prods,
        "batches": batches,
        "demand": demand,
        "inbound": [],
        "inbound_file_provided": False,
        "routes": routes,
        "capacities": [
            {
                "location_id": loc["id"],
                "receiving": None if loc["role"] == hub else 400,
                "dispatch": 20_000 if loc["role"] == hub else 1_500,
                "storage": None,
            }
            for loc in locs
        ],
        "global_handling": 150_000,
        "cost_budget_minor": None,
        "reserves": [],
        "retail_weights": {"w_exp": 1, "w_lost": 1} if mode == "retail" else None,
        "planning_days": None,
        "policy": None,
        "vulnerability": [],
        "assumptions": ["synthetic benchmark network (fictional)"],
    }
    if mode == "pantry":
        payload |= pantry_fields(locs, hubs)
    return ORInputV3.model_validate(payload)


def pantry_fields(locs, hubs):
    """CR-w1-solver-1 fields plus vulnerability for every pantry (EGP needs both)."""
    from app.schemas.v1_planning import DEFAULT_PANTRY_POLICY

    rng = random.Random(SEED + 1)
    return {
        "planning_days": 3,
        "policy": DEFAULT_PANTRY_POLICY.model_dump(mode="json"),
        "vulnerability": [
            {
                "location_id": loc["id"],
                "poverty_rate": f"{rng.randint(5, 40) / 100:.2f}",
                "snap_rate": f"{rng.randint(5, 40) / 100:.2f}",
                "source": "manual",
            }
            for loc in locs[hubs:]
        ],
    }


def _batch(bid, lid, pid, qty, expiry):
    return {
        "id": bid,
        "location_id": lid,
        "product_id": pid,
        "quantity": qty,
        "expiry_date": None if expiry is None else expiry.isoformat(),
        "non_expiring": expiry is None,
    }


def peak_rss_mb() -> float:
    own = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    children = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    return round(max(own, children) / 1024, 1)  # Linux reports KiB


def source(evidence: Path) -> dict:
    """The commit this run measures; the tree must be clean apart from the evidence file itself."""

    def git(*argv):
        return subprocess.run(
            ["git", *argv], cwd=Path(__file__).parent, capture_output=True, text=True, check=True
        ).stdout.strip()

    changed = [
        line[3:]
        for line in git("status", "--porcelain").splitlines()
        if Path(git("rev-parse", "--show-toplevel"), line[3:]).resolve() != evidence.resolve()
    ]
    return {"commit": git("rev-parse", "HEAD"), "tree_clean": not changed}


def run(args) -> dict:
    from app.services.optimization.compare import compare_methods
    from app.services.optimization.verify import verify_plan

    started = time.monotonic()
    scenario = generate(args.locations, args.products, args.mode)
    built = time.monotonic() - started
    record = {
        "mode": args.mode.upper(),
        "seed": SEED,
        "machine": {"platform": platform.platform(), "cpus_allowed": len(os.sched_getaffinity(0))},
        "recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
        **source(args.out),
        "size": {
            "locations": len(scenario.locations),
            "products": len(scenario.products),
            "batches": len(scenario.batches),
            "demand_series": len(scenario.demand),
            "routes": len(scenario.routes),
        },
        "generate_s": round(built, 1),
        "ceilings_s": {"method": 330, "comparison": 690},
        "methods": [],
    }
    for measure in ("UNITS", "USD") if args.mode == "retail" else ("UNITS",):
        t0 = time.monotonic()
        result = compare_methods(
            scenario,
            METHODS[args.mode],
            measure,
            scenario_id="00000000-0000-4000-8000-00000000b005",
            scenario_hash="0" * 64,
        )
        wall = time.monotonic() - t0
        for m in result.methods:
            union = verify_plan(scenario, m.transfers) if m.verified else None
            record["methods"].append(
                {
                    "measure": measure,
                    "method": m.method,
                    "native_status": m.native_status,
                    "product_status_counts": dict(
                        Counter(p.native_status or p.label or "baseline" for p in m.products)
                    ),
                    "verified": m.verified,
                    "failure_reason": m.failure_reason,
                    "transfers": len(m.transfers),
                    "union_check": None
                    if union is None
                    else {
                        "passed": union.passed,
                        "violations": list(union.violations),
                    },
                }
            )
        record.setdefault("comparison_wall_s", {})[measure] = round(wall, 1)
    record["peak_rss_mb"] = peak_rss_mb()
    record["total_s"] = round(time.monotonic() - started, 1)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--locations", type=int, default=100)
    parser.add_argument("--products", type=int, default=500)
    parser.add_argument("--mode", choices=("retail", "pantry"), required=True)
    parser.add_argument("--out", type=Path, default=EVIDENCE)
    args = parser.parse_args()
    record = run(args)
    existing = json.loads(args.out.read_text()) if args.out.exists() else {}
    existing[record["mode"]] = record
    args.out.write_text(json.dumps(existing, indent=2) + "\n")
    print(
        json.dumps({k: record[k] for k in ("mode", "comparison_wall_s", "peak_rss_mb", "total_s")})
    )


if __name__ == "__main__":
    main()
