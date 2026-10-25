"""Export/check the public contract offline; no database or inference initialization."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import app  # noqa: E402


def document():
    return json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--stdout", action="store_true")
    group.add_argument("--check", type=Path)
    args = parser.parse_args()
    value = document()
    if args.stdout:
        sys.stdout.write(value)
        return 0
    if not args.check.exists() or args.check.read_text(encoding="utf-8-sig") != value:
        print("OpenAPI drift: regenerate the checked-in public contract.", file=sys.stderr)
        return 1
    print("OpenAPI matches the application schemas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
