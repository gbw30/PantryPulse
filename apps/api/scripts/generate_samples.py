"""Write data/templates/examples/*.csv (the Pantry sample on a fixed date, W3-P03) and
data/templates/examples/retail/*.csv (the Retail sample, CR-w3-samples-3).

The examples are the `kind=example` template downloads, so they always match the samples.
Run after changing the sample generator; `--check` only reports drift (the tests use it).

    uv run --frozen python scripts/generate_samples.py [--check]
"""

import sys
from pathlib import Path
from typing import get_args

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.schemas.v1_networks import TemplateName  # noqa: E402
from app.schemas.v1_planning import NetworkMode  # noqa: E402
from app.services.imports.templates import template_csv  # noqa: E402

EXAMPLES = Path(__file__).resolve().parents[3] / "data" / "templates" / "examples"
FOLDERS: dict[NetworkMode, Path] = {"PANTRY": EXAMPLES, "RETAIL": EXAMPLES / "retail"}


def main(check: bool) -> int:
    drift, names = [], get_args(TemplateName)
    for mode, folder in FOLDERS.items():
        if not check:
            folder.mkdir(parents=True, exist_ok=True)
        for name in names:
            path, data = folder / f"{name}.csv", template_csv(name, "example", mode).encode()
            # bytes, not read_text: universal newlines would hide a CRLF checkout
            if not path.exists() or path.read_bytes() != data:
                drift.append(path.relative_to(EXAMPLES).as_posix())
                if not check:
                    path.write_bytes(data)
    if check and drift:
        print(f"examples differ from the generator: {', '.join(drift)}; "
              "run scripts/generate_samples.py")
        return 1
    print(f"{'checked' if check else 'wrote'} {len(FOLDERS) * len(names)} examples "
          f"({len(drift)} changed)")
    return 0


if __name__ == "__main__":
    sys.exit(main("--check" in sys.argv[1:]))
