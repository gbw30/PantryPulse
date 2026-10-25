"""Offline OR qualification; deterministic SIMULATED inputs, no application services.

Run with apps/api/.venv/bin/python scripts/or/qualify.py --output PATH.
The JSON is evidence, not a new policy or a production performance guarantee.
"""

import argparse
import copy
import gc
import hashlib
import json
import platform
import resource
import sys
import time
from datetime import UTC, datetime, timedelta
from fractions import Fraction
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps/api"))

import ortools
from app.schemas.or_inputs import (
    DemandModifier,
    ORInputPackage,
    ORPolicy,
    ORScenarioPayload,
)
from app.services.optimization.candidates import prepare_problem
from app.services.optimization.canonical import operational_hash
from app.services.optimization.classical_gp import attach_classical
from app.services.optimization.compare import assemble
from app.services.optimization.constraints import build_physical_model
from app.services.optimization.egp_pi_inspired import attach_research
from app.services.optimization.numerics import audit_model
from app.services.optimization.offline import bounded_methods
from app.services.optimization.scenario import freeze_scenario
from app.services.optimization.service import DEFAULT_SETTINGS

METHODS = ("CLASSICAL_GP", "EGP_PI_INSPIRED")
MODES = ("HUB_ONLY", "HUB_AND_PANTRY")
DATA = ROOT / "data/demo/or-v2"


def fixture(name="six-beneficiary-v2"):
    return ORScenarioPayload.model_validate_json(
        (DATA / f"{name}.snapshot.json").read_text()
    )


def freeze(original, *, package=None, policy=None, mode=None, days=None):
    package = package or original.package
    modifiers = tuple(
        DemandModifier(
            site_id=s.id,
            product_id=p.id,
            mode="CENTRAL",
            multiplier="1",
            buffer_fraction=None,
        )
        for s in package.sites
        for p in package.products
    )
    return freeze_scenario(
        package,
        policy or original.policy,
        transfer_mode=mode or original.transfer_mode,
        planning_days=days or original.planning_days,
        modifiers=modifiers,
        intent="CURRENT",
        expected_source_revision=package.source_revision_token,
    )


def upper_scope(*, numeric=False, mode="HUB_ONLY"):
    """All size bounds together; numeric variant also reaches lot/goal/cost bounds."""
    original = fixture()
    raw = original.package.model_dump()
    revision = (
        "qualification-upper-numeric-v1" if numeric else "qualification-upper-size-v1"
    )
    raw["source_revision_token"] = revision
    first = raw["first_planning_date"]
    uid = lambda value: UUID(int=value)  # stable identities across runs/modes
    cap = lambda value: {
        "original": value,
        "fixed_used": 0,
        "residual": value,
        "source_revision": revision,
    }
    sites = []
    for i in range(14):
        site = copy.deepcopy(raw["sites"][0])
        site.update(
            id=uid(10 + i),
            role="HUB" if i < 2 else "BENEFICIARY",
            name=f"SIMULATED qualification site {i}",
            source_revision=revision,
        )
        sites.append(site)
    raw["sites"] = sites
    for p in raw["products"]:
        p["source_revision"] = revision
    forecasts, inventory, arrivals, reserves, attributes, capacities, routes = (
        [],
        [],
        [],
        [],
        [],
        [],
        [],
    )
    for i, site in enumerate(sites):
        capacities.append(
            {
                "site_id": site["id"],
                "source": cap(10_000_000 if numeric else 80),
                "receiving": [cap(1_000_000 if numeric else 50) for _ in range(7)],
                "storage": [cap(25_600_000 if numeric else 100) for _ in range(7)],
            }
        )
        if i >= 2:
            row = copy.deepcopy(raw["vulnerability_attributes"][0])
            row["site_id"] = site["id"]
            for j, score in enumerate(row["scores"]):
                score.update(
                    score_bp=((i * 1703 + j * 3089) % 10001),
                    raw_note="SIMULATED qualification score",
                    transformation_version=revision,
                )
            attributes.append(row)
        for j, product in enumerate(raw["products"]):
            forecast = copy.deepcopy(raw["forecasts"][0])
            forecast.update(
                id=uid(1000 + 2 * i + j),
                site_id=site["id"],
                product_id=product["id"],
                unit=product["unit"],
                source_revision=revision,
            )
            for d, point in enumerate(forecast["days"]):
                quantity = 0 if i < 2 else (1 if i < 6 else 3)
                if numeric and i >= 2:
                    quantity = [33333, 33333, 33334, 0, 0, 0, 0][d]
                point["central_literal"] = str(quantity)
            forecasts.append(forecast)
            reserves.append(
                {"site_id": site["id"], "product_id": product["id"], "floors": [0] * 7}
            )
            if i < 6:
                for k in range(19):
                    lot = copy.deepcopy(raw["inventory"][0])
                    units = 100000 if numeric else 1
                    # Some hub stock expires before late ETA; donors retain all seven days.
                    life = (1 + k % 3) if i < 2 and k < 6 else 8
                    lot.update(
                        id=uid(2000 + 38 * i + 19 * j + k),
                        site_id=site["id"],
                        product_id=product["id"],
                        unit=product["unit"],
                        physical_units=units,
                        free_units=units,
                        source_line_id=uid(5000 + 38 * i + 19 * j + k),
                        expires_on=first + timedelta(days=life),
                        source_revision=revision,
                    )
                    inventory.append(lot)
            arrivals.append(
                {
                    "id": uid(8000 + 2 * i + j),
                    "source_line_id": uid(9000 + 2 * i + j),
                    "site_id": site["id"],
                    "product_id": product["id"],
                    "unit": product["unit"],
                    "units": 100000 if numeric else 1,
                    "available_on": first + timedelta(days=3),
                    "expires_on": first + timedelta(days=8),
                    "expiry_kind": "DATED",
                    "eligibility": "ELIGIBLE",
                    "confirmed": True,
                    "already_posted": False,
                    "source_revision": revision,
                }
            )
    for i, source in enumerate(sites):
        for j, destination in enumerate(sites):
            if i == j:
                continue
            routes.append(
                {
                    "id": uid(10000 + 14 * i + j),
                    "source_id": source["id"],
                    "destination_id": destination["id"],
                    "enabled": True,
                    "eta_days": (i + j) % 3,
                    "capacity": cap(300000 if numeric else 12),
                    "cost_unit": "SIM_CREDIT",
                    "costs": [
                        {
                            "product_id": p["id"],
                            "cost_minor": 1000000 if numeric else 1 + (i + j + k) % 5,
                        }
                        for k, p in enumerate(raw["products"])
                    ],
                }
            )
    raw.update(
        forecasts=forecasts,
        inventory=inventory,
        confirmed_arrivals=arrivals,
        reserves=reserves,
        vulnerability_attributes=attributes,
        routes=routes,
        capacities={
            "sites": capacities,
            "global_handling": cap(1_440_000 if numeric else 144),
            "cost_budget_minor": None,
        },
        provenance_warnings=("SIMULATED upper-bound qualification only",),
    )
    content = {
        k: v for k, v in raw.items() if k not in {"source_refs", "source_manifest_hash"}
    }
    raw["source_refs"] = tuple(
        ref.model_copy(
            update={"revision": revision, "content_hash": operational_hash(content)}
        )
        for ref in original.package.source_refs
    )
    raw["source_manifest_hash"] = operational_hash(raw["source_refs"])
    return freeze(
        original, package=ORInputPackage.model_validate(raw), mode=mode, days=3
    )


def summarize(outcome):
    result = outcome.model_dump(mode="json")
    report = result.pop("verification")
    result.pop("candidate")
    if report:
        result["verification_passed"] = report["passed"]
        result["metrics"] = report["metrics"]
    return result


def check_case(name, outcomes):
    """Independent literal/limiting expectations, beyond production replay."""
    expected = {
        "ap-ablation-v2-full": ((1, 0), Fraction(19, 8)),
        "ap-ablation-v2-gamma0": ((0, 1), Fraction(2)),
        "rp-ablation-v2-full": ((0, 1), Fraction(11, 4)),
        "rp-ablation-v2-gamma0": ((1, 0), Fraction(21, 8)),
    }
    if name in expected:
        vector, objective = expected[name]
        research = outcomes[1]
        goals = sorted(
            research.verification.metrics.goals, key=lambda g: str(g.site_id)
        )
        if (tuple(g.fulfilled for g in goals), research.objective.fraction()) != (
            vector,
            objective,
        ):
            raise RuntimeError("QUALIFICATION_LITERAL_ORACLE_MISMATCH")
    if (
        name in {"lambda-0", "no-research-terms"}
        and outcomes[0].objective != outcomes[1].objective
    ):
        raise RuntimeError("QUALIFICATION_CLASSICAL_LIMIT_MISMATCH")
    for outcome in outcomes:
        metrics = outcome.verification.metrics
        if name == "thresholds-20000" and any(g.ap or g.rp for g in metrics.goals):
            raise RuntimeError("QUALIFICATION_MAX_THRESHOLD_FLAG")
        if name == "caps-10000" and (
            metrics.ap_excess.numerator or metrics.rp_excess.numerator
        ):
            raise RuntimeError("QUALIFICATION_FULL_CAP_EXCESS")


def measure(name, scenario, *, profile=False):
    profiles = []
    if profile:
        problem = prepare_problem(scenario)
        for method in METHODS:
            started = time.monotonic()
            physical = build_physical_model(problem)
            (attach_classical if method == METHODS[0] else attach_research)(physical)
            audit = audit_model(physical.model)
            profiles.append(
                {
                    "method": method,
                    "variables": len(physical.model.proto.variables),
                    "constraints": len(physical.model.proto.constraints),
                    "maximum_activity": audit["maximum_activity"],
                    "limit_exclusive": audit["limit_exclusive"],
                    "physical_fingerprint": physical.fingerprint,
                    "build_audit_seconds": time.monotonic() - started,
                }
            )
            del physical, audit
            gc.collect()
    started = time.monotonic()
    outcomes = bounded_methods(scenario, METHODS, DEFAULT_SETTINGS)
    bounded_seconds = time.monotonic() - started
    pair = assemble(scenario, outcomes, expected_settings=DEFAULT_SETTINGS)
    wall_seconds = time.monotonic() - started
    if pair.outcome != "SUCCEEDED":
        raise RuntimeError(
            f"QUALIFICATION_FAILED:{name}:{[(x.outcome, x.error_code) for x in outcomes]}"
        )
    if profile and any(
        p["physical_fingerprint"] != o.physical_fingerprint
        for p, o in zip(profiles, outcomes, strict=True)
    ):
        raise RuntimeError("QUALIFICATION_PHYSICAL_IDENTITY_MISMATCH")
    check_case(name, outcomes)
    return {
        "name": name,
        "transfer_mode": str(scenario.transfer_mode),
        "operational_hash": scenario.operational_hash,
        "policy_hash": scenario.policy_hash,
        "source_manifest_hash": scenario.package.source_manifest_hash,
        "policy": scenario.policy.model_dump(mode="json"),
        "outcome": str(pair.outcome),
        "dimensions": {
            "beneficiaries": sum(
                s.role == "BENEFICIARY" for s in scenario.package.sites
            ),
            "hubs": sum(s.role == "HUB" for s in scenario.package.sites),
            "products": len(scenario.package.products),
            "routes": len(scenario.package.routes),
            "resources": len(scenario.package.inventory)
            + len(scenario.package.confirmed_arrivals),
            "planning_days": scenario.planning_days,
            "maximum_goal_target": max(
                sum(d.units for d in s.days[: scenario.planning_days])
                for s in scenario.demand
            ),
        },
        "bounded_pair_seconds": bounded_seconds,
        "pair_including_assembly_seconds": wall_seconds,
        "child_peak_rss_bytes_since_process_start": resource.getrusage(
            resource.RUSAGE_CHILDREN
        ).ru_maxrss
        * 1024,
        "profiles": profiles,
        "methods": [summarize(x) for x in outcomes],
        "common_differences": pair.common_differences,
    }


def sensitivity_cases():
    """Change one declared policy grid at a time; primary defaults are never overwritten."""
    original = fixture()
    changes = [
        ("lambda-0", {"lambda_percent": 0}),
        ("lambda-50", {"lambda_percent": 50}),
        ("beta-0", {"beta_percent": 0}),
        ("beta-100", {"beta_percent": 100}),
        ("thresholds-0", {"ap_threshold": 0, "rp_threshold": 0}),
        ("thresholds-20000", {"ap_threshold": 20000, "rp_threshold": 20000}),
        ("caps-0", {"ap_cap_bp": 0, "rp_cap_bp": 0}),
        ("caps-10000", {"ap_cap_bp": 10000, "rp_cap_bp": 10000}),
        ("gamma-1000", {"gamma_ap_percent": 1000, "gamma_rp_percent": 1000}),
        (
            "no-research-terms",
            {"lambda_percent": 0, "gamma_ap_percent": 0, "gamma_rp_percent": 0},
        ),
        ("cost-waste-10000", {"epsilon_cost_bp": 10000, "epsilon_waste_bp": 10000}),
        (
            "need-only",
            {
                "coefficients": [
                    {"attribute_id": "need", "percent": 100},
                    {"attribute_id": "access", "percent": 0},
                ]
            },
        ),
    ]
    for name, updates in changes:
        raw = original.policy.model_dump()
        raw.update(updates, purpose="ABLATION", version=f"qualification-{name}-v1")
        yield name, freeze(original, policy=ORPolicy.model_validate(raw))
    # The original two attribute columns coincide. Use a separately fingerprinted
    # synthetic disagreement case so coefficient sensitivity is observable.
    raw = original.package.model_dump()
    revision = "qualification-attribute-disagreement-v1"
    raw["source_revision_token"] = revision
    for row in raw["vulnerability_attributes"]:
        scores = {x["attribute_id"]: x for x in row["scores"]}
        scores["access"].update(
            score_bp=10000 - scores["need"]["score_bp"],
            raw_note="SIMULATED reversed attribute for sensitivity",
            transformation_version=revision,
        )
    content = {
        k: v for k, v in raw.items() if k not in {"source_refs", "source_manifest_hash"}
    }
    raw["source_refs"] = tuple(
        ref.model_copy(
            update={"revision": revision, "content_hash": operational_hash(content)}
        )
        for ref in original.package.source_refs
    )
    raw["source_manifest_hash"] = operational_hash(raw["source_refs"])
    mixed = ORInputPackage.model_validate(raw)
    for name, need_percent in (
        ("mixed-attributes-50", 50),
        ("mixed-attributes-need", 100),
        ("mixed-attributes-access", 0),
    ):
        policy = original.policy.model_dump()
        policy.update(
            purpose="ABLATION",
            version=f"qualification-{name}-v1",
            coefficients=[
                {"attribute_id": "need", "percent": need_percent},
                {"attribute_id": "access", "percent": 100 - need_percent},
            ],
        )
        yield (
            name,
            freeze(original, package=mixed, policy=ORPolicy.model_validate(policy)),
        )
    for name, field in (
        ("ap-ablation-v2", "gamma_ap_percent"),
        ("rp-ablation-v2", "gamma_rp_percent"),
    ):
        base = fixture(name)
        yield name + "-full", base
        raw = base.policy.model_dump()
        raw.update(
            purpose="ABLATION", version=f"qualification-{name}-gamma0", **{field: 0}
        )
        yield name + "-gamma0", freeze(base, policy=ORPolicy.model_validate(raw))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--suite", choices=("scale", "sensitivity", "all"), default="all"
    )
    args = parser.parse_args()
    cases = []
    if args.suite in ("scale", "all"):
        cases.append(("six-default", fixture(), True))
        cases.extend(
            (
                f"upper-{'numeric' if numeric else 'size'}-{mode}",
                upper_scope(numeric=numeric, mode=mode),
                True,
            )
            for numeric in (False, True)
            for mode in MODES
        )
    if args.suite in ("sensitivity", "all"):
        cases.extend((name, scenario, False) for name, scenario in sensitivity_cases())
    evidence = {
        "schema_version": "or-qualification-v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "source_kind": "SIMULATED",
        "code_sha256": {
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(
                [
                    *ROOT.glob("apps/api/app/services/optimization/*.py"),
                    *ROOT.glob("apps/api/app/schemas/or_*.py"),
                    ROOT / "scripts/or/qualify.py",
                ]
            )
        },
        "python": platform.python_version(),
        "platform": platform.platform(),
        "ortools": ortools.__version__,
        "settings": DEFAULT_SETTINGS,
        "settings_hash": operational_hash(DEFAULT_SETTINGS),
        "memory_scope": "Linux maximum individual method-child RSS, cumulative since qualification process start; not aggregate process-tree memory",
        "cases": [],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for name, scenario, profile in cases:
        print(f"Qualifying {name}", file=sys.stderr, flush=True)
        evidence["cases"].append(measure(name, scenario, profile=profile))
        args.output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
