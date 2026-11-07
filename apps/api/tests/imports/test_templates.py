# covers: V1-A06
"""Blank templates and the in-app column guide (W1-D03)."""

import io
from datetime import date
from pathlib import Path
from typing import get_args

import pytest

from app.schemas.v1_imports import ImportSettings
from app.schemas.v1_networks import TemplateName
from app.services.imports.columns import COLUMNS, header
from app.services.imports.templates import template_catalog, template_csv
from app.services.imports.validate import validate_files
from app.services.v1_errors import NotImplementedV1

BLANK_DIR = Path(__file__).resolve().parents[4] / "data" / "templates" / "blank"
NAMES: tuple[TemplateName, ...] = get_args(TemplateName)


@pytest.mark.parametrize("mode", [None, "PANTRY", "RETAIL"])
def test_every_column_has_guide_entry(mode):
    catalog = template_catalog(mode)
    assert [t.name for t in catalog.templates] == list(NAMES)
    for template in catalog.templates:
        assert template.description.strip()
        assert [c.name for c in template.columns] == [c for c, _ in COLUMNS[template.name]]
        for column in template.columns:
            assert column.meaning.strip() and column.effect_on_plan.strip()
            assert column.unit is None or column.unit.strip()


def test_required_flags_follow_the_spec():
    catalog = {t.name: t for t in template_catalog(None).templates}
    assert {n for n, t in catalog.items() if t.required} == {
        "locations", "products", "inventory", "demand_history"}
    quantity = next(c for c in catalog["demand_history"].columns if c.name == "quantity")
    assert "blank" in quantity.meaning and "never" in quantity.meaning  # blank = unknown, not 0


@pytest.mark.parametrize("name", NAMES)
def test_blank_templates_are_header_only(name):
    text = (BLANK_DIR / f"{name}.csv").read_text(encoding="utf-8")
    assert text == header(name) + "\n"
    assert template_csv(name, "blank") == text


@pytest.mark.parametrize("name", NAMES)
def test_blank_templates_match_validator_columns(name):
    settings = ImportSettings(mode="PANTRY", timezone="America/New_York",
                              as_of_date=date(2026, 11, 4))
    files = {n: io.BytesIO(template_csv(n, "blank").encode()) for n in NAMES}
    report = validate_files(files, settings)
    assert not [e for e in report.errors if e.file == name and e.line == 1], report.errors


def test_type_values_per_mode():
    def location_types(mode):
        locations = next(t for t in template_catalog(mode).templates if t.name == "locations")
        return next(c for c in locations.columns if c.name == "type").allowed_values

    assert location_types("PANTRY") == ("hub", "pantry")
    assert location_types("RETAIL") == ("distribution_center", "store")
    assert set(location_types(None)) == {"hub", "pantry", "distribution_center", "store"}


def test_guide_states_single_timezone_and_blank_capacity_rule():
    catalog = template_catalog("PANTRY")
    notes = " ".join(catalog.notes)
    assert "capacity not provided — no limit assumed" in notes
    assert "one timezone" in notes.lower()
    basis = next(c for t in catalog.templates if t.name == "demand_history"
                 for c in t.columns if c.name == "basis")
    assert "sales (undercounts demand when shelves were empty)" in basis.meaning


def test_examples_kind_returns_501_until_w3():
    with pytest.raises(NotImplementedV1) as raised:
        template_csv("locations", "example")
    assert raised.value.details == {"task": "W3-P03"}
    assert not any(t.example_available for t in template_catalog(None).templates)


def test_template_routes_answer_through_the_api():
    from types import SimpleNamespace
    from uuid import UUID

    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.routers.forecasts import presenter, runtime

    app = create_app()
    app.dependency_overrides[runtime] = lambda: SimpleNamespace()
    app.dependency_overrides[presenter] = lambda: SimpleNamespace(
        organization_id=UUID(int=1), actor="local")
    client = TestClient(app)
    catalog = client.get("/api/v1/templates", params={"mode": "RETAIL"})
    assert catalog.status_code == 200
    assert catalog.json()["mode"] == "RETAIL"
    blank = client.get("/api/v1/templates/inventory.csv")
    assert blank.status_code == 200
    assert blank.headers["content-type"].startswith("text/csv")
    assert blank.text == header("inventory") + "\n"
