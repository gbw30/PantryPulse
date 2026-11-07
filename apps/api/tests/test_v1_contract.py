# covers: V1-A22
"""W0-08 contract freeze: every v1 route exists, unbuilt routes answer 501 naming their task,
uploads stream past the 64 KB boundary, and v2's OpenAPI stays byte-identical."""

import json
import re
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import create_app
from app.routers.forecasts import presenter, runtime
from app.schemas.v1_envelope import UPLOAD_CAP_BYTES
from app.schemas.v1_planning import (
    METHODS_BY_MODE,
    ORInputV3,
    ScenarioOptions,
    require_methods_for_mode,
)
from app.services.jobs.registry import InputRejected

ROOT = Path(__file__).resolve().parents[3]
NET, IMP, CMP, LOC, JOB = (str(uuid4()) for _ in range(5))


def _shape(path):
    return re.sub(r"\{[^}]+\}", "{}", path)


def _readme_routes():
    text = (ROOT / "docs/plans/v1/README.md").read_text()
    section = text.split("**HTTP routes**", 1)[1].split("**Job kinds**", 1)[0]
    return {
        (method, _shape("/api/v1" + path))
        for method, path in re.findall(r"`(GET|POST|PUT|DELETE) (/[^`\s?]+)", section)
    }


@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[runtime] = lambda: SimpleNamespace()
    app.dependency_overrides[presenter] = lambda: SimpleNamespace(
        organization_id=UUID(int=1), actor="local"
    )
    return TestClient(app, raise_server_exceptions=False)


def test_every_v1_route_in_openapi():
    expected = _readme_routes()
    assert len(expected) >= 25
    paths = create_app().openapi()["paths"]
    actual = {(m.upper(), _shape(p)) for p, ops in paths.items() for m in ops}
    assert expected - actual == set()


def test_v2_openapi_unchanged():
    committed = json.loads((ROOT / "packages/contracts/openapi.json").read_text())
    current = create_app().openapi()
    v2_paths = {p: current["paths"].get(p) for p in committed["paths"]}
    assert v2_paths == committed["paths"]
    for name, schema in committed["components"]["schemas"].items():
        assert current["components"]["schemas"].get(name) == schema, name


CSV = {"Content-Type": "text/csv"}
KEYED = {"Idempotency-Key": "contract-test-1"}
NEW_NETWORK = {"name": "N", "mode": "PANTRY", "timezone": "America/New_York"}
ACTIONS = f"/networks/{NET}/comparisons/{CMP}/methods/EQUAL_SHARE"
STUBS = [
    ("GET", "/networks", None, None, "W1-D05"),
    ("GET", f"/networks/{NET}", None, None, "W1-D05"),
    ("GET", "/templates", None, None, "W1-D03"),
    ("GET", "/templates/locations.csv?kind=blank", None, None, "W1-D03"),
    ("GET", "/templates/locations.csv?kind=example", None, None, "W3-P03"),
    ("POST", "/imports", {"network": NEW_NETWORK}, None, "W1-D05"),
    ("POST", f"/imports/{IMP}/files/demand_history", b"a" * 70_000, CSV, "W1-D04"),
    ("POST", f"/imports/{IMP}/commit", {}, KEYED, "W1-D05"),
    ("GET", f"/imports/{IMP}", None, None, "W1-D05"),
    ("GET", f"/networks/{NET}/enrichment", None, None, "W1-D06"),
    ("POST", f"/networks/{NET}/enrichment/retry", {}, KEYED, "W1-D06"),
    ("PUT", f"/networks/{NET}/locations/{LOC}/attributes", {"excluded": True}, None, "W1-D06"),
    ("GET", f"/networks/{NET}/routes", None, None, "W1-D07"),
    ("GET", "/settings", None, None, "W1-D08"),
    ("PUT", "/settings/google-maps-key", {"key": "k"}, None, "W1-D08"),
    ("DELETE", "/settings/google-maps-key", None, None, "W1-D08"),
    ("POST", f"/networks/{NET}/routes/google-preview", {}, None, "W1-D08"),
    ("POST", f"/networks/{NET}/routes/google-fetch", {}, KEYED, "W1-D08"),
    ("GET", f"/networks/{NET}/danger?forecast_run_id={JOB}", None, None, "W3-F05"),
    ("GET", f"/forecasts/{JOB}/backtest", None, None, "W3-F03"),
    ("GET", f"/networks/{NET}/comparisons/{CMP}", None, None, "W1-S04"),
    ("GET", f"{ACTIONS}/actions", None, None, "W1-S06"),
    ("POST", f"{ACTIONS}/export", {"action_ids": ["t1"]}, None, "W1-S07"),
]


@pytest.mark.parametrize(("method", "path", "body", "headers", "task"), STUBS)
def test_unimplemented_routes_return_501_with_task_id(client, method, path, body, headers, task):
    kwargs = {"content": body} if isinstance(body, bytes) else {"json": body}
    response = client.request(method, "/api/v1" + path, headers=headers, **kwargs)
    assert response.status_code == 501, response.text
    error = response.json()["error"]
    assert error["code"] == "NOT_IMPLEMENTED"
    assert error["details"] == {"task": task}
    assert response.json()["request_id"] == response.headers["x-request-id"]


def test_network_scoped_job_routes_return_501(client):
    scenario = {"dataset_version_id": str(uuid4()), "forecast_run_id": str(uuid4()),
                "transfer_mode": "HUB_ONLY"}
    for path, body, task in (
        (f"/networks/{NET}/scenarios", scenario, "W1-D09"),
        (f"/networks/{NET}/forecasts", {"dataset_version_id": str(uuid4())}, "W3-F03"),
        (f"/networks/{NET}/comparisons",
         {"scenario_id": str(uuid4()), "methods": ["NO_TRANSFERS"], "measure": "UNITS"}, "W1-S04"),
    ):
        response = client.post("/api/v1" + path, json=body, headers=KEYED)
        assert response.status_code == 501, (path, response.text)
        assert response.json()["error"]["details"] == {"task": task}


def test_json_routes_keep_the_64kb_boundary(client):
    response = client.post(
        f"/api/v1/imports/{IMP}/commit", content=b"{" + b" " * 70_000 + b"}", headers=KEYED
    )
    assert response.status_code == 413


def test_upload_rejects_declared_size_over_cap(client):
    response = client.post(
        f"/api/v1/imports/{IMP}/files/demand_history", content=b"a",
        headers={**CSV, "Content-Length": str(UPLOAD_CAP_BYTES + 1)},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "INPUT_TOO_LARGE"


def test_upload_requires_csv_and_a_template_name(client):
    url = f"/api/v1/imports/{IMP}/files"
    as_json = {"Content-Type": "application/json"}
    assert client.post(f"{url}/demand_history", content=b"{}", headers=as_json).status_code == 422
    assert client.post(f"{url}/secrets", content=b"a", headers=CSV).status_code == 422


@pytest.mark.anyio
async def test_bounded_chunks_stops_at_cap():
    from app.routers.v1_imports import bounded_chunks

    async def source():
        for _ in range(4):
            yield b"abc"

    assert [c async for c in bounded_chunks(source(), 12)] == [b"abc"] * 4
    with pytest.raises(InputRejected) as rejected:
        [c async for c in bounded_chunks(source(), 11)]
    assert rejected.value.code == "INPUT_TOO_LARGE"


def _scenario(locations, products, **overrides):
    hub = {"id": "H0", "name": "Hub", "role": "hub"}
    sites = [hub] + [{"id": f"P{i}", "name": f"Pantry {i}", "role": "pantry"}
                     for i in range(1, locations)]
    payload = {
        "network_id": str(uuid4()), "organization_id": str(uuid4()),
        "dataset_version_id": str(uuid4()), "forecast_run_id": str(uuid4()),
        "mode": "PANTRY", "transfer_mode": "HUB_ONLY", "timezone": "America/New_York",
        "snapshot_as_of": "2026-11-05", "first_planning_date": "2026-11-06",
        "locations": sites,
        "products": [{"id": f"SKU{i}", "name": f"Item {i}", "unit": "case",
                      "handling_units_per_unit": 1, "unit_value_usd": None}
                     for i in range(products)],
        "batches": [], "demand": [], "inbound": [], "inbound_file_provided": False,
        "routes": [], "capacities": [], "global_handling": None, "cost_budget_minor": None,
        "reserves": [], "retail_weights": None, "vulnerability": [], "assumptions": [],
    }
    return {**payload, **overrides}


def test_scenario_caps():
    ORInputV3.model_validate(_scenario(100, 500))
    for locations, products, limit in ((101, 1, "100"), (2, 501, "500")):
        with pytest.raises(ValidationError, match=f"at most {limit} items"):
            ORInputV3.model_validate(_scenario(locations, products))


def test_scenario_roles_match_mode():
    with pytest.raises(ValidationError, match="ROLE_NOT_IN_MODE"):
        ORInputV3.model_validate(
            _scenario(3, 1, mode="RETAIL", retail_weights={"w_exp": 1, "w_lost": 1})
        )


def test_retail_weights_required_only_in_retail():
    with pytest.raises(ValidationError, match="RETAIL_WEIGHTS"):
        ORInputV3.model_validate(_scenario(2, 1, retail_weights={"w_exp": 1, "w_lost": 1}))


def test_method_sets_per_mode():
    assert METHODS_BY_MODE["PANTRY"] == (
        "NO_TRANSFERS", "EQUAL_SHARE", "MOST_URGENT_FIRST", "CLASSICAL_GP", "EGP_PI_INSPIRED")
    assert METHODS_BY_MODE["RETAIL"] == ("NO_TRANSFERS", "SOONEST_EXPIRY_FIRST", "RETAIL_OPTIMIZED")
    require_methods_for_mode("RETAIL", ["NO_TRANSFERS", "RETAIL_OPTIMIZED"])
    with pytest.raises(InputRejected) as rejected:
        require_methods_for_mode("PANTRY", ["RETAIL_OPTIMIZED"])
    assert rejected.value.code == "METHOD_NOT_IN_MODE"


def test_transfer_mode_still_required():
    with pytest.raises(ValidationError, match="transfer_mode"):
        ScenarioOptions.model_validate(
            {"dataset_version_id": str(uuid4()), "forecast_run_id": str(uuid4())})
    with pytest.raises(ValidationError, match="transfer_mode"):
        payload = _scenario(2, 1)
        del payload["transfer_mode"]
        ORInputV3.model_validate(payload)


def test_scenario_is_frozen_and_dates_ordered():
    with pytest.raises(ValidationError, match="FIRST_PLANNING_DATE"):
        ORInputV3.model_validate(_scenario(2, 1, first_planning_date=str(date(2026, 11, 5))))
