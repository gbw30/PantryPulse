"""OFFLINE bounded sequential pair; exits 0 both, 5 partial, 4 neither, 2 bad source."""

import argparse

from app.services.optimization.compare import assemble
from app.services.optimization.offline import bounded_methods
from app.services.optimization.service import DEFAULT_SETTINGS
from scripts.or_common import snapshot, write


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        value = snapshot(args.snapshot)
    except (ValueError, OSError, TypeError):
        return 2
    result = assemble(
        value,
        bounded_methods(value, ("CLASSICAL_GP", "EGP_PI_INSPIRED")),
        expected_settings=DEFAULT_SETTINGS,
    )
    write(args.output, {"execution": "OFFLINE", "comparison": result.model_dump(mode="json")})
    return {"SUCCEEDED": 0, "PARTIAL": 5, "FAILED": 4}[result.outcome]


if __name__ == "__main__":
    raise SystemExit(main())
