"""Contract/worker tests for PP-45; database behavior has separate integration tests."""

from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import app
from app.schemas.forecast_api import ForecastRequest
from app.services.forecasting.preparation import prepare
from app.services.jobs.contracts import PRODUCTION_PROFILE, StepOutcome, StepStatus
from app.services.jobs.registry import ClassifiedStepFailure, ExecutionContext, PublicationRejected
from app.workers.forecasting import REGISTRATION
from app.workers.registries import load_registry
from scripts.forecasting_fixture import build_fixture


def frozen():
    history, policy, _origins, as_of = build_fixture()
    return prepare(history, data_cutoff_date=date(2026, 9, 28), snapshot_as_of=as_of, policy=policy)


def test_production_registry_has_real_forecast():
    assert load_registry("production").get("forecast.v1") is REGISTRATION


def test_public_request_requires_policy_and_has_no_client_organization():
    with pytest.raises(ValidationError):
        ForecastRequest(
            source_id=uuid4(), data_cutoff_date="2026-09-28", snapshot_as_of="2026-10-01T00:00:00Z"
        )
    with pytest.raises(ValidationError):
        ForecastRequest(organization_id=uuid4())


def test_worker_computes_seven_days_without_database_access():
    inputs = frozen()
    handler = REGISTRATION.handler
    validated = handler.validate_input({"forecast_input": inputs.model_dump(mode="json")})
    steps = handler.steps(validated, PRODUCTION_PROFILE)
    assert steps[0].name == "primary"
    result = handler.execute_step(
        "primary", validated, (), ExecutionContext(uuid4(), uuid4(), "primary", 298, 15)
    )
    package = REGISTRATION.publisher.validate(
        validated, [StepOutcome("primary", StepStatus.COMPLETED, output=result)]
    )
    assert package["forecast_output"]["ready_for_publication"] is True
    assert len(package["forecast_output"]["series"]) == 26
    assert all(len(row["points"]) == 7 for row in package["forecast_output"]["series"])


def test_publisher_rejects_missing_or_tampered_output():
    inputs = frozen()
    payload = {"forecast_input": inputs.model_dump(mode="json")}
    with pytest.raises(PublicationRejected):
        REGISTRATION.publisher.validate(payload, [])
    with pytest.raises(PublicationRejected):
        REGISTRATION.publisher.validate(
            payload, [StepOutcome("primary", StepStatus.COMPLETED, output={"forecast_output": {}})]
        )


def test_classified_fallback_is_supervised_and_programming_errors_escape(monkeypatch):
    from app.services.forecasting.adapters.base import ProviderError
    from app.services.forecasting.adapters.seasonal_naive import SeasonalNaiveAdapter

    inputs = frozen()
    payload = {"forecast_input": inputs.model_dump(mode="json")}
    context = ExecutionContext(uuid4(), uuid4(), "primary", 298, 15)

    def provider_failure(*_args):
        raise ProviderError("TEST_PROVIDER_FAILURE", "Classified test failure")

    monkeypatch.setattr(SeasonalNaiveAdapter, "predict", provider_failure)
    with pytest.raises(ClassifiedStepFailure):
        REGISTRATION.handler.execute_step("primary", payload, (), context)
    failure = StepOutcome(
        "primary",
        StepStatus.FAILED,
        error_code="PRIMARY_SERIES_UNAVAILABLE",
        fallback_eligible=True,
    )
    result = REGISTRATION.handler.execute_step("fallback", payload, [failure.summary()], context)
    package = REGISTRATION.publisher.validate(
        payload, [failure, StepOutcome("fallback", StepStatus.COMPLETED, output=result)]
    )
    assert package["forecast_output"]["input_hash"] == inputs.input_hash
    assert all(
        s["fallback_used"] and s["actual_provider"]["name"] == "MOVING_AVERAGE"
        for s in package["forecast_output"]["series"]
    )
    with pytest.raises(PublicationRejected):
        REGISTRATION.publisher.validate(
            payload,
            [
                StepOutcome("primary", StepStatus.FAILED, fallback_eligible=False),
                StepOutcome("fallback", StepStatus.COMPLETED, output=result),
            ],
        )

    def bug(*_args):
        raise RuntimeError("Programming error must not become fallback success")

    monkeypatch.setattr(SeasonalNaiveAdapter, "predict", bug)
    with pytest.raises(RuntimeError):
        REGISTRATION.handler.execute_step("primary", payload, (), context)


def test_publisher_rejects_false_model_provenance():
    payload = {"forecast_input": frozen().model_dump(mode="json")}
    result = REGISTRATION.handler.execute_step(
        "primary", payload, (), ExecutionContext(uuid4(), uuid4(), "primary", 298, 15)
    )
    output = result["forecast_output"]
    for row in output["series"]:
        row["actual_provider"]["name"] = "CHRONOS2"
    output["actual_providers"] = ["CHRONOS2"]
    with pytest.raises(PublicationRejected):
        REGISTRATION.publisher.validate(
            payload, [StepOutcome("primary", StepStatus.COMPLETED, output=result)]
        )


def test_schema_export_is_offline_and_health_unchanged():
    with TestClient(app) as client:
        assert client.get("/api/v1/health").json() == {"status": "ok", "scope": "process"}
        schema = client.get("/openapi.json").json()
        assert "/api/v1/forecasts" in schema["paths"]
        assert "/api/v1/forecasts/{job_id}" in schema["paths"]
        assert client.post("/api/v1/forecasts", json={}).status_code in {401, 503}
