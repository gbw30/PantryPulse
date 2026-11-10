# covers: V1-A06
"""Template examples are generated from the samples, so the two always match: the Pantry sample
for Pantry mode (W3-P03) and the Retail sample for Retail mode (CR-w3-samples-3)."""

import io
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import get_args
from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.schemas.v1_imports import ImportSettings
from app.schemas.v1_networks import TemplateName
from app.schemas.v1_planning import NetworkMode
from app.services.imports.templates import EXAMPLE_AS_OF, template_catalog, template_csv
from app.services.imports.validate import validate_files
from app.services.samples.pantry import pantry_sample
from app.services.samples.retail import retail_sample

API = Path(__file__).resolve().parents[2]
EXAMPLES = API.parents[1] / "data" / "templates" / "examples"
NAMES: tuple[TemplateName, ...] = get_args(TemplateName)
MODES: dict[NetworkMode, tuple[Path, Callable]] = {
    "PANTRY": (EXAMPLES, pantry_sample), "RETAIL": (EXAMPLES / "retail", retail_sample)}


def committed(mode: NetworkMode) -> dict[TemplateName, io.BytesIO]:
    folder = MODES[mode][0]
    return {name: io.BytesIO((folder / f"{name}.csv").read_bytes()) for name in NAMES}


@pytest.mark.parametrize("mode", MODES)
def test_example_files_equal_generator_output(mode):
    folder, build = MODES[mode]
    sample = build(EXAMPLE_AS_OF)
    for name in NAMES:
        # bytes, not read_text: universal newlines would hide a CRLF checkout
        data = (folder / f"{name}.csv").read_bytes()
        assert data == template_csv(name, "example", mode).encode() == sample.files[
            name].encode(), name


def test_generator_check_reports_no_drift():
    # The script regenerates exactly what is committed, for both modes.
    result = subprocess.run([sys.executable, "scripts/generate_samples.py", "--check"],
                            cwd=API, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stdout + result.stderr


def test_every_template_has_example_in_each_mode():
    for folder, build in MODES.values():
        assert sorted(p.stem for p in folder.glob("*.csv")) == sorted(NAMES), folder
        # every example is filled: a header and at least one row (V1-SPEC §6.1)
        files = build(EXAMPLE_AS_OF).files
        assert all(text.count("\n") >= 2 for text in files.values())
        assert set(files) == set(NAMES), folder
    for mode in MODES:
        assert all(t.example_available for t in template_catalog(mode).templates), mode
    # Without a mode the page can't know which example set fits, so it offers none.
    assert not any(t.example_available for t in template_catalog(None).templates)
    assert template_csv("locations", "example") == template_csv("locations", "example", "PANTRY")


def test_catalog_offers_examples_only_where_they_validate():
    for mode in MODES:
        report = validate_files(committed(mode), ImportSettings(
            mode=mode, timezone="America/New_York", as_of_date=None))
        offered = {t.example_available for t in template_catalog(mode).templates}
        assert offered == {report.ok}, (mode, report.errors[:5])


@pytest.mark.parametrize("mode", MODES)
def test_examples_validate_clean(mode):
    # No as-of date given: it defaults to the day after the last history date, as for a user.
    settings = ImportSettings(mode=mode, timezone="America/New_York", as_of_date=None)
    report = validate_files(committed(mode), settings)
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
    for mode, (folder, _) in MODES.items():
        for name in NAMES:
            response = client.get(f"/api/v1/templates/{name}.csv",
                                  params={"kind": "example", "mode": mode})
            assert response.status_code == 200, (mode, response.text[:200])
            assert response.headers["content-type"].startswith("text/csv")
            assert response.content == (folder / f"{name}.csv").read_bytes(), (mode, name)
