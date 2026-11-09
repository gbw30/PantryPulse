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
from app.schemas.or_inputs import AttributeCoefficient
from app.schemas.v1_envelope import UPLOAD_CAP_BYTES
from app.schemas.v1_imports import ImportCreated, ImportStatus, RowError
from app.schemas.v1_networks import BacktestResult, Network, NetworkForecastRun
from app.schemas.v1_planning import (
    DEFAULT_PANTRY_POLICY,
    METHODS_BY_MODE,
    ActionEffect,
    ORInputV3,
    RetailWeights,
    SavedComparisonV3,
    ScenarioOptions,
    require_methods_for_mode,
    resolve_window_and_policy,
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
    ("GET", f"/networks/{NET}/danger?forecast_run_id={JOB}", None, None, "W3-F05"),
    ("GET", f"/networks/{NET}/projection?forecast_run_id={JOB}&location_id=P-1", None, None,
     "W3-F05"),
    ("GET", f"/forecasts/{JOB}/backtest", None, None, "W3-F03"),
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
    for path, body, task in (
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
    payload = {**payload, **overrides}
    pantry = payload["mode"] == "PANTRY"
    payload.setdefault("planning_days", 3 if pantry else None)
    payload.setdefault("policy", DEFAULT_PANTRY_POLICY.model_dump(mode="json") if pantry else None)
    return payload


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


# CR-w1-solver-1 (Gabriel, 2026-11-07): the Pantry window (BD-50) and EGP policy (V1-SPEC §6.2)
# are frozen in the scenario, so a saved scenario replays exactly.
def test_pantry_scenario_freezes_window_and_policy():
    frozen = ORInputV3.model_validate(_scenario(2, 1, planning_days=2))
    assert frozen.planning_days == 2 and frozen.policy == DEFAULT_PANTRY_POLICY
    for missing in ("planning_days", "policy"):
        payload = _scenario(2, 1)
        del payload[missing]
        with pytest.raises(ValidationError, match=missing):  # explicit, no default
            ORInputV3.model_validate(payload)
    for empty in ({"planning_days": None}, {"policy": None}):
        with pytest.raises(ValidationError, match="WINDOW_AND_POLICY_ONLY_IN_PANTRY"):
            ORInputV3.model_validate(_scenario(2, 1, **empty))
    for days in (0, 4):
        with pytest.raises(ValidationError, match="planning_days"):
            ORInputV3.model_validate(_scenario(2, 1, planning_days=days))


def test_retail_scenario_has_no_window_or_policy():
    def retail(**extra):
        payload = _scenario(2, 1, mode="RETAIL", retail_weights={"w_exp": 1, "w_lost": 1},
                            **extra)
        payload["locations"] = [{"id": "D0", "name": "DC", "role": "distribution_center"},
                                {"id": "S1", "name": "Store 1", "role": "store"}]
        return payload

    ORInputV3.model_validate(retail())
    for extra in ({"planning_days": 3}, {"policy": DEFAULT_PANTRY_POLICY.model_dump(mode="json")}):
        with pytest.raises(ValidationError, match="WINDOW_AND_POLICY_ONLY_IN_PANTRY"):
            ORInputV3.model_validate(retail(**extra))


def test_policy_weights_only_v1_vulnerability_attributes():
    policy = DEFAULT_PANTRY_POLICY.model_dump(mode="json")
    assert {c["attribute_id"] for c in policy["coefficients"]} == {"poverty_rate", "snap_rate"}
    policy["coefficients"] = [{"attribute_id": "need", "percent": 50},
                              {"attribute_id": "access", "percent": 50}]
    with pytest.raises(ValidationError, match="UNKNOWN_POLICY_ATTRIBUTE"):
        ORInputV3.model_validate(_scenario(2, 1, policy=policy))


def test_default_pantry_policy_keeps_connected_flow_values():
    snapshot = json.loads((ROOT / "data/demo/or-vp-v2/source-snapshot.json").read_text())
    connected = {k: v for k, v in snapshot["policy"].items() if k != "coefficients"}
    default = DEFAULT_PANTRY_POLICY.model_dump(mode="json")
    assert {k: v for k, v in default.items() if k != "coefficients"} == connected
    assert [c["percent"] for c in default["coefficients"]] == [
        c["percent"] for c in snapshot["policy"]["coefficients"]]


def test_scenario_options_resolve_window_and_policy():
    ids = {"dataset_version_id": str(uuid4()), "forecast_run_id": str(uuid4()),
           "transfer_mode": "HUB_ONLY"}
    with pytest.raises(InputRejected) as rejected:
        resolve_window_and_policy("PANTRY", ScenarioOptions.model_validate(ids))
    assert rejected.value.code == "PLANNING_DAYS_REQUIRED"
    chosen = ScenarioOptions.model_validate({**ids, "planning_days": 2})
    assert resolve_window_and_policy("PANTRY", chosen) == (2, DEFAULT_PANTRY_POLICY)
    edited = DEFAULT_PANTRY_POLICY.model_copy(update={"lambda_percent": 40})
    own = ScenarioOptions.model_validate({**ids, "planning_days": 1, "policy": edited})
    assert resolve_window_and_policy("PANTRY", own) == (1, edited)
    assert resolve_window_and_policy("RETAIL", ScenarioOptions.model_validate(ids)) == (None, None)
    with pytest.raises(InputRejected) as rejected:
        resolve_window_and_policy("RETAIL", chosen)
    assert rejected.value.code == "WINDOW_AND_POLICY_ONLY_IN_PANTRY"
    need = {"coefficients": (AttributeCoefficient(attribute_id="need", percent=100),)}
    bad = ScenarioOptions.model_validate(
        {**ids, "planning_days": 2, "policy": DEFAULT_PANTRY_POLICY.model_copy(update=need)})
    with pytest.raises(InputRejected) as rejected:  # verifier F4 on PR #103
        resolve_window_and_policy("PANTRY", bad)
    assert rejected.value.code == "UNKNOWN_POLICY_ATTRIBUTE"


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
    assert "22 v1 examples valid" in result.stdout


def _example(name):
    return json.loads((ROOT / f"packages/contracts/examples/v1/{name}.json").read_text())


def test_retail_weights_need_one_positive_weight():  # E-1 (Gabriel, 2026-11-07)
    with pytest.raises(ValidationError, match="RETAIL_WEIGHTS_ALL_ZERO"):
        RetailWeights(w_exp=0, w_lost=0)
    assert RetailWeights(w_exp=0, w_lost=1).w_lost == 1
    assert RetailWeights(w_exp=1, w_lost=0).w_exp == 1


def test_action_effect_names_the_product_unit():  # CR-w1-web-5
    effect = _example("DecisionActions")["actions"][0]["effect"]
    assert ActionEffect.model_validate(effect).unit == "case"
    for bad in ({k: v for k, v in effect.items() if k != "unit"}, {**effect, "unit": ""}):
        with pytest.raises(ValidationError):
            ActionEffect.model_validate(bad)


def test_saved_comparison_carries_the_scenario_notes():  # CR-w1-web-6 (a)
    saved = SavedComparisonV3.model_validate(_example("SavedComparisonV3"))
    scenario = _example("ScenarioV3")
    assert saved.scenario_id == UUID(scenario["id"])
    assert saved.assumptions == tuple(scenario["payload"]["assumptions"])
    assert saved.inbound_file_provided is scenario["payload"]["inbound_file_provided"]
    for field in ("assumptions", "inbound_file_provided"):
        body = _example("SavedComparisonV3")
        del body[field]
        with pytest.raises(ValidationError):
            SavedComparisonV3.model_validate(body)


def test_network_says_whether_inbound_was_provided():  # CR-w1-web-6 (b)
    imported, pending = (Network.model_validate(n) for n in _example("NetworkList")["networks"])
    assert imported.inbound_file_provided is True
    assert pending.inbound_file_provided is None  # no dataset version yet
    with pytest.raises(ValidationError, match="bool_type"):  # strict, like SavedComparisonV3
        Network.model_validate({**_example("Network"), "inbound_file_provided": 1})
    with pytest.raises(ValidationError, match="INBOUND_FLAG_NEEDS_A_DATASET_VERSION"):
        Network.model_validate({**_example("Network"), "inbound_file_provided": None})
    with pytest.raises(ValidationError, match="INBOUND_FLAG_NEEDS_A_DATASET_VERSION"):
        Network.model_validate(
            {**_example("NetworkList")["networks"][1], "inbound_file_provided": False}
        )


def test_network_forecast_series_say_how_they_were_made():  # CR-w1-web-4 (a)
    run = _example("NetworkForecastRun")
    series = NetworkForecastRun.model_validate(run).model_dump()["series"]
    by_status = {s["status"]: s for s in series}
    assert len(by_status["AVAILABLE"]["points"]) == 7
    kinds = {(s["kind"], s["basis"]) for s in run["series"]}
    assert ("donation", None) in kinds and ("demand", "sales") in kinds
    available = next(s for s in run["series"] if s["status"] == "AVAILABLE")
    missing = next(s for s in run["series"] if s["status"] == "INSUFFICIENT_DATA")
    for bad in (
        {**available, "actual_provider": None},  # no unnamed method
        {**available, "points": available["points"][:6]},
        {**available, "reason": "should not be here"},
        {**available, "fallback_used": True, "fallback_reason": None},
        {**missing, "points": available["points"]},  # never forecast from zeros
        {**missing, "reason": None},
        {**available, "kind": "donation"},  # a donation series has no demand basis
        {**available, "basis": None},
        {**missing, "fallback_used": True, "fallback_reason": "INSUFFICIENT_DATA"},  # no method
    ):
        with pytest.raises(ValidationError):
            NetworkForecastRun.model_validate({**run, "series": [bad]})
    shifted = [
        {**pt, "day": f"2026-11-{int(pt['day'][-2:]) + 1:02d}"} for pt in available["points"]
    ]
    for series in ([available, available], [{**available, "points": shifted}]):
        with pytest.raises(ValidationError):  # one series per key; days are the 7 after cutoff
            NetworkForecastRun.model_validate({**run, "series": series})


def test_backtest_rolls_up_per_location_and_unit():  # CR-w1-web-4 (b)
    result = _example("BacktestResult")
    rows = BacktestResult.model_validate(result).locations
    assert {(r.location_id, r.unit) for r in rows} >= {("P-12", "case")}
    with pytest.raises(ValidationError, match="DUPLICATE_LOCATION_UNIT"):
        row = rows[0].model_dump(mode="json")
        BacktestResult.model_validate({**result, "locations": [row, row]})
