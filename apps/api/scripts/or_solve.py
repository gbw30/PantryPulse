"""OFFLINE bounded native method; exits 0 verified, 4 no vector, 2 invalid source."""

import argparse

from app.services.optimization.offline import bounded_methods
from app.services.optimization.settings import solver_settings
from scripts.or_common import snapshot, write


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--method", required=True, choices=["CLASSICAL_GP", "EGP_PI_INSPIRED"])
    parser.add_argument("--output", required=True)
    parser.add_argument("--search-seconds", type=int, default=120)
    args = parser.parse_args(argv)
    try:
        value = snapshot(args.snapshot)
        settings = solver_settings(args.search_seconds)
    except (ValueError, OSError, TypeError):
        return 2
    result = bounded_methods(value, (args.method,), settings)[0]
    write(args.output, {"execution": "OFFLINE", "result": result.model_dump(mode="json")})
    return 0 if result.outcome == "VERIFIED" else 4


if __name__ == "__main__":
    raise SystemExit(main())
