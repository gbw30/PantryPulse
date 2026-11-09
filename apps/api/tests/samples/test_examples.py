# covers: V1-A06
"""Template examples are generated from the Pantry sample, so the two always match (W3-P03)."""

import io
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import get_args
from uuid import UUID

from fastapi.testclient import TestClient

from app.schemas.v1_imports import ImportSettings
from app.schemas.v1_networks import TemplateName
from app.services.imports.templates import EXAMPLE_AS_OF, template_catalog, template_csv
from app.services.imports.validate import validate_files
from app.services.samples.pantry import pantry_sample

API = Path(__file__).resolve().parents[2]
EXAMPLES = API.parents[1] / "data" / "templates" / "examples"
NAMES: tuple[TemplateName, ...] = get_args(TemplateName)


def test_example_files_equal_generator_output():
    sample = pantry_sample(EXAMPLE_AS_OF)
    for name in NAMES:
        text = (EXAMPLES / f"{name}.csv").read_text(encoding="utf-8")
        assert text == template_csv(name, "example") == sample.files[name], name
    # The script regenerates exactly what is committed.
    result = subprocess.run([sys.executable, "scripts/generate_samples.py", "--check"],
                            cwd=API, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


def test_every_template_has_example():
    assert sorted(p.stem for p in EXAMPLES.glob("*.csv")) == sorted(NAMES)
    for mode in (None, "PANTRY"):
        assert all(t.example_available for t in template_catalog(mode).templates)


def test_catalog_offers_examples_only_where_they_validate():
    """The one example set is the Pantry sample: a Retail import page must not offer it."""
    for mode in ("PANTRY", "RETAIL"):
        files = {name: io.BytesIO((EXAMPLES / f"{name}.csv").read_bytes()) for name in NAMES}
        report = validate_files(files, ImportSettings(mode=mode, timezone="America/New_York",
                                                      as_of_date=None))
        offered = {t.example_available for t in template_catalog(mode).templates}
        assert offered == {report.ok}, mode


def test_examples_validate_clean():
    files = {name: io.BytesIO((EXAMPLES / f"{name}.csv").read_bytes()) for name in NAMES}
    # No as-of date given: it defaults to the day after the last history date, as for a user.
    settings = ImportSettings(mode="PANTRY", timezone="America/New_York", as_of_date=None)
    report = validate_files(files, settings)
    assert report.ok, report.errors[:5]
    assert report.rows.as_of_date == EXAMPLE_AS_OF


def test_get_template_example_returns_csv():
    from app.main import create_app
    from app.routers.forecasts import presenter, runtime

    app = create_app()
    app.dependency_overrides[runtime] = lambda: SimpleNamespace()
    app.dependency_overrides[presenter] = lambda: SimpleNamespace(
        organization_id=UUID(int=1), actor="local")
    client = TestClient(app)
    for name in NAMES:
        response = client.get(f"/api/v1/templates/{name}.csv", params={"kind": "example"})
        assert response.status_code == 200, response.text
        assert response.headers["content-type"].startswith("text/csv")
        assert response.text == (EXAMPLES / f"{name}.csv").read_text(encoding="utf-8")
