# covers: V1-A22
"""W0-08 contract freeze: every v1 route exists, unbuilt routes answer 501 naming their task,
uploads stream past the 64 KB boundary, and v2's OpenAPI stays byte-identical."""

import hashlib
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
from app.schemas.v1_imports import ImportCreated, ImportStatus, RowError
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


# sha256 of the v2 surface (41 paths + the 114 schemas they reach) at base 7067b0b. Pinned here,
# not read from packages/contracts/openapi.json, because regenerating that file would hide drift.
V2_SURFACE_SHA256 = "7be5531b0829ea6febfeeea71d60f65af71b3ac58a7614bab5d5bd8d5ed5980e"


def test_v2_openapi_unchanged():
    doc = create_app().openapi()
    v1 = {path for _, path in _readme_routes()}
    paths = sorted(p for p in doc["paths"] if _shape(p) not in v1)
    schemas, reached, todo = doc["components"]["schemas"], set(), [doc["paths"][p] for p in paths]
    while todo:
        for ref in re.findall(r'"#/components/schemas/([^"]+)"', json.dumps(todo.pop())):
            if ref not in reached:
                reached.add(ref)
                todo.append(schemas[ref])
    surface = {"paths": {p: doc["paths"][p] for p in paths},
               "schemas": {n: schemas[n] for n in sorted(reached)}}
    assert (len(paths), len(reached)) == (41, 114)
    digest = hashlib.sha256(json.dumps(surface, sort_keys=True).encode()).hexdigest()
    assert digest == V2_SURFACE_SHA256


CSV = {"Content-Type": "text/csv"}
KEYED = {"Idempotency-Key": "contract-test-1"}
NEW_NETWORK = {"name": "N", "mode": "PANTRY", "timezone": "America/New_York"}
ACTIONS = f"/networks/{NET}/comparisons/{CMP}/methods/EQUAL_SHARE"
STUBS = [
    ("GET", "/templates/locations.csv?kind=example", None, None, "W3-P03"),
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


BATCH = {"id": "B1", "location_id": "P1", "product_id": "SKU0", "quantity": 1,
         "expiry_date": None, "non_expiring": True}
INBOUND = {**BATCH, "id": "I1", "arrival_date": "2026-11-07"}
DEMAND = {"location_id": "P1", "product_id": "SKU0", "basis": "demand",
          "actual_provider": "seasonal_naive", "fallback_reason": None,
          "central_literals": ["1"] * 7, "targets": [1] * 7}
ROUTE = {"from_location_id": "H0", "to_location_id": "P1", "travel_days": 1,
         "method": "routes_csv", "road_miles": None,
         "cost_per_handling_unit_usd": "2", "capacity_per_batch": 10}
RESERVE = {"location_id": "P1", "product_id": "SKU0", "floor": 0}
CAPACITY = {"location_id": "P1", "receiving": None, "dispatch": None, "storage": None}
VULNERABILITY = {"location_id": "P1", "poverty_rate": "0.1", "snap_rate": "0.1",
                 "source": "manual"}
ROWS = {"batches": [BATCH], "inbound": [INBOUND], "inbound_file_provided": True,
        "demand": [DEMAND], "routes": [ROUTE], "reserves": [RESERVE],
        "capacities": [CAPACITY], "vulnerability": [VULNERABILITY]}


def test_scenario_with_one_row_of_each_kind_is_valid():
    ORInputV3.model_validate(_scenario(2, 1, **ROWS))


@pytest.mark.parametrize("field", ["batches", "inbound", "demand", "routes", "reserves",
                                   "capacities", "vulnerability"])
def test_scenario_rejects_duplicate_rows(field):
    rows = {**ROWS, field: ROWS[field] * 2}
    with pytest.raises(ValidationError, match="DUPLICATE_ROW"):
        ORInputV3.model_validate(_scenario(2, 1, **rows))


@pytest.mark.parametrize("field", ["capacities", "vulnerability"])
def test_scenario_rejects_unknown_location_in_site_rows(field):
    rows = {**ROWS, field: [{**ROWS[field][0], "location_id": "NOPE"}]}
    with pytest.raises(ValidationError, match="UNKNOWN_REFERENCE"):
        ORInputV3.model_validate(_scenario(2, 1, **rows))


@pytest.mark.parametrize("arrival", ["2026-11-05", "2026-11-13"])
def test_scenario_rejects_inbound_outside_horizon(arrival):
    rows = {**ROWS, "inbound": [{**INBOUND, "arrival_date": arrival}]}
    with pytest.raises(ValidationError, match="INBOUND_OUTSIDE_HORIZON"):
        ORInputV3.model_validate(_scenario(2, 1, **rows))


def test_scenario_rejects_inbound_rows_without_inbound_file():
    with pytest.raises(ValidationError, match="INBOUND_WITHOUT_FILE"):
        ORInputV3.model_validate(_scenario(2, 1, **{**ROWS, "inbound_file_provided": False}))


def test_route_keeps_routes_csv_cost_and_capacity():
    route = ORInputV3.model_validate(_scenario(2, 1, **ROWS)).routes[0]
    assert (route.cost_per_handling_unit_usd, route.capacity_per_batch) == ("2", 10)
    for bad in ({"cost_per_handling_unit_usd": "-1"}, {"capacity_per_batch": -1}):
        with pytest.raises(ValidationError):
            ORInputV3.model_validate(_scenario(2, 1, **{**ROWS, "routes": [{**ROUTE, **bad}]}))


def test_planning_starts_the_day_after_the_snapshot():
    with pytest.raises(ValidationError, match="FIRST_PLANNING_DATE"):
        ORInputV3.model_validate(_scenario(2, 1, first_planning_date="2026-12-01"))


def _status(**overrides):
    example = ROOT / "packages/contracts/examples/v1/ImportStatus.json"
    return {**json.loads(example.read_text()), **overrides}


def test_new_network_import_has_no_network_until_it_succeeds():
    assert ImportCreated.model_validate({"import_id": IMP, "network_id": None}).network_id is None
    ImportStatus.model_validate(_status(network_id=None))  # failed first import: no network
    done = _status(phase="done", failure=None, network_id=None, dataset_version_id=JOB,
                   as_of_date="2026-11-05")
    with pytest.raises(ValidationError, match="DONE_NEEDS_NETWORK_AND_VERSION"):
        ImportStatus.model_validate(done)


def test_failed_import_says_why_and_what_to_do():
    failure = _status()["failure"]
    assert failure["message"].startswith("Import failed")
    assert "nothing was saved" in failure["message"]
    assert failure["reason"] and failure["next_steps"]
    with pytest.raises(ValidationError, match="FAILURE_IFF_FAILED"):
        ImportStatus.model_validate(_status(failure=None))
    with pytest.raises(ValidationError, match="FAILURE_IFF_FAILED"):
        ImportStatus.model_validate(_status(phase="validating"))
    row = _status()["errors"][0]
    assert row["fix"]
    with pytest.raises(ValidationError, match="fix"):
        RowError.model_validate({k: v for k, v in row.items() if k != "fix"})


@pytest.mark.parametrize("field", ["message", "reason", "next_steps", "fix"])
def test_failure_guidance_is_never_blank(field):
    status = _status()
    if field == "fix":
        status["errors"] = [{**status["errors"][0], "fix": "   "}]
    elif field == "next_steps":
        status["failure"] = {**status["failure"], "next_steps": [" "]}
    else:
        status["failure"] = {**status["failure"], field: " "}
    with pytest.raises(ValidationError):
        ImportStatus.model_validate(status)


def test_examples_validate():
    import subprocess
    import sys

    script = Path(__file__).resolve().parents[1] / "scripts/validate_contract_examples.py"
    result = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "18 v1 examples valid" in result.stdout
