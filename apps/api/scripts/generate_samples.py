"""Write data/templates/examples/*.csv: the Pantry sample on a fixed date (W3-P03).

The examples are the `kind=example` template downloads, so they always match the sample.
Run after changing the sample generator; `--check` only reports drift (the tests use it).

    uv run --frozen python scripts/generate_samples.py [--check]
"""

import sys
from pathlib import Path
from typing import get_args

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.v1_networks import TemplateName  # noqa: E402
from app.services.imports.templates import template_csv  # noqa: E402

EXAMPLES = Path(__file__).resolve().parents[3] / "data" / "templates" / "examples"


def main(check: bool) -> int:
    drift = []
    EXAMPLES.mkdir(parents=True, exist_ok=True)
    for name in get_args(TemplateName):
        path, text = EXAMPLES / f"{name}.csv", template_csv(name, "example")
        if not path.exists() or path.read_text(encoding="utf-8") != text:
            drift.append(path.name)
            if not check:
                path.write_text(text, encoding="utf-8", newline="")
    if check and drift:
        print(f"examples differ from the generator: {', '.join(drift)}; "
              "run scripts/generate_samples.py")
        return 1
    print(f"{'checked' if check else 'wrote'} {len(get_args(TemplateName))} examples "
          f"({len(drift)} changed)")
    return 0


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv[1:]))
