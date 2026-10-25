"""Strict source/scenario validation; exit 0 valid, 2 invalid, 1 unexpected failure."""

import argparse
import json
from pathlib import Path

from app.schemas.or_inputs import ORInputPackage
from app.services.optimization.canonical import operational_hash
from scripts.or_common import snapshot, write


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args(argv)
    try:
        data = json.loads(Path(args.input).read_text())
        value = (
            snapshot(args.input)
            if data.get("schema_version") == "or-scenario-v1"
            else ORInputPackage.model_validate(data)
        )
        write(
            args.report,
            {
                "valid": True,
                "schema_version": value.schema_version,
                "content_hash": operational_hash(value),
            },
        )
        return 0
    except (ValueError, OSError, TypeError):
        write(args.report, {"valid": False, "error_code": "INVALID_OR_INPUT"})
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
