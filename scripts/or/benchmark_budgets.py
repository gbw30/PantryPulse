"""Reproducible Linux budget sweep on identical dense frozen inputs, one worker."""
import argparse
import hashlib
import json
import platform
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "apps/api"))


def code_identity():
    paths = sorted((ROOT / "apps/api/app/services/optimization").glob("*.py"))
    paths += sorted((ROOT / "apps/api/app/schemas").glob("or_*.py"))
    paths += [Path(__file__), Path(__file__).with_name("qualify.py")]
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def child():
    import resource
    from app.schemas.or_inputs import ORScenarioPayload
    from app.services.optimization.service import solve_one
    request = json.load(sys.stdin)
    result = solve_one(ORScenarioPayload.model_validate(request["scenario"]), request["method"], request["settings"])
    print(json.dumps({"method_result": result.model_dump(mode="json"),
        "peak_rss_kib": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss}, allow_nan=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--child", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.child:
        child()
        return
    if platform.system() != "Linux" or args.output is None:
        parser.error("Linux and --output are required")
    from qualify import upper_scope
    from app.services.optimization.canonical import operational_hash
    from app.services.optimization.process import run_child
    from app.services.optimization.settings import solver_settings
    evidence = dict(schema_version="or-budget-benchmark-v2", started_at=datetime.now(UTC).isoformat(),
        platform=platform.platform(), python=platform.python_version(), code_sha256=code_identity(),
        scenarios={}, runs=[])
    args.output.parent.mkdir(parents=True, exist_ok=True)
    for mode in ("HUB_ONLY", "HUB_AND_PANTRY"):
        scenario = upper_scope(mode=mode)
        evidence["scenarios"][mode] = scenario.model_dump(mode="json")
        for seconds in (15, 30, 60, 120, 300):
            settings = solver_settings(seconds)
            for method in ("CLASSICAL_GP", "EGP_PI_INSPIRED"):
                if code_identity() != evidence["code_sha256"]:
                    raise RuntimeError("Source changed during benchmark; preserve this partial evidence")
                request = json.dumps(dict(scenario=scenario.model_dump(mode="json"), method=method, settings=settings)).encode()
                start = time.monotonic()
                result = run_child([sys.executable, str(Path(__file__).resolve()), "--child"], request,
                    deadline=start + seconds + 30)
                row = dict(mode=mode, method=method, settings=settings, settings_hash=operational_hash(settings),
                    operational_hash=scenario.operational_hash, wall_seconds=time.monotonic()-start,
                    process_reason=result.reason, process_returncode=result.returncode)
                if result.returncode == 0 and not result.reason:
                    row.update(json.loads(result.stdout))
                evidence["runs"].append(row)
                args.output.write_text(json.dumps(evidence, indent=2) + "\n")
                outcome = row.get("method_result", {})
                print(f"{mode} {method} {seconds}s: {outcome.get('native_status', result.reason)} gap={outcome.get('gap')}", flush=True)
    evidence["completed_at"] = datetime.now(UTC).isoformat()
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")


if __name__ == "__main__":
    main()
