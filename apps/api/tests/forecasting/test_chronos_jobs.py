"""Chronos contract/admission/provenance checks without heavy model dependencies."""

import copy
import subprocess
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.repositories.jobs import QueueRepository
from app.schemas.forecast_api import ForecastRequest
from app.services import chronos_runtime
from app.services.chronos_runtime import CHRONOS_CONTRACT, bind_policy, policy_capability
from app.services.forecasting.adapters.base import ProviderError
from app.services.forecasting.adapters.chronos2 import (
    ADAPTER_VERSION,
    PACKAGE_VERSION,
    ChronosConfig,
)
from app.services.forecasting.preparation import prepare, validate_input
from app.services.forecasting.schemas import ForecastInput, ForecastPoint
from app.services.jobs.contracts import (
    PRODUCTION_PROFILE,
    AdmissionOutcome,
    StepOutcome,
    StepStatus,
)
from app.services.jobs.policies import supervisor_advertisement
from app.services.jobs.registry import (
    ClassifiedStepFailure,
    ExecutionContext,
    PublicationIdentity,
    PublicationRejected,
)
from app.workers.chronos_forecasting import REGISTRATION
from app.workers.forecasting import REGISTRATION as BASELINE
from app.workers.process_driver import PosixProcessDriver
from app.workers.registries import load_registry
from scripts.forecasting_fixture import build_fixture

REVISION = "a" * 40


def enable(monkeypatch):
    monkeypatch.setenv("PP_CHRONOS_ENABLED", "1")
    monkeypatch.setenv("PP_CHRONOS_REVISION", REVISION)
    monkeypatch.setenv("PP_CHRONOS_MODEL_CACHE", "/operator/cache")


def payload(monkeypatch, *, fallback=False):
    enable(monkeypatch)
    history, policy, _, as_of = build_fixture()
    policy = bind_policy(policy.model_copy(update={"allow_fallback": fallback}))
    inputs = prepare(
        history, data_cutoff_date=date(2026, 9, 28), snapshot_as_of=as_of, policy=policy
    )
    return {"forecast_input": inputs.model_dump(mode="json")}


def context():
    return ExecutionContext(uuid4(), uuid4(), "primary", 298, 15)


class Model:
    identity = ChronosConfig(REVISION).identity

    def predict(self, series, inputs):
        if series.scope.key.target_type == "DONATION":
            raise ProviderError("INVALID_PROVIDER_OUTPUT", "Deliberate native-output boundary case")
        return tuple(
            ForecastPoint(
                day=inputs.data_cutoff_date + timedelta(days=i),
                central_estimate=10.0,
                estimate_kind="MEDIAN",
                p10=8.0,
                p50=10.0,
                p90=12.0,
                interval_method="MODEL_QUANTILES",
            )
            for i in range(1, 8)
        )


def test_original_baseline_fixture_hash_is_unchanged():
    # Independently reproduced from the untouched main archive before schema edits.
    history, policy, _, as_of = build_fixture()
    inputs = prepare(
        history, data_cutoff_date=date(2026, 9, 28), snapshot_as_of=as_of, policy=policy
    )
    assert inputs.input_hash == "515f61754ca862e1ad6e40885feced72be40b11251d2122d1a539e77f3190891"
    assert validate_input(ForecastInput.model_validate_json(inputs.model_dump_json())) == inputs
    assert set(policy.model_dump()) == {
        "policy_version",
        "sparse_window_days",
        "sparse_min_samples",
        "strategy",
        "allow_fallback",
        "allow_fulfilled_proxy",
        "allow_mixed_proxy_history",
        "preprocessing_version",
        "postprocessing_version",
        "adapter_version",
        "provider_package_version",
        "checkpoint",
        "checkpoint_revision",
    }
    assert policy.adapter_version == "core-v1"


def test_api_and_registry_import_without_optional_model_dependencies():
    code = (
        "import sys; from app.main import app; from app.workers.production import REGISTRY; "
        "assert 'forecast.chronos.v1' in REGISTRY.contracts(); "
        "assert not {'torch','chronos','huggingface_hub'}.intersection(sys.modules); "
        "assert 'forecast.chronos.v1' not in REGISTRY.execution_advertisement()[0]"
    )
    subprocess.run([sys.executable, "-c", code], cwd=Path(__file__).parents[2], check=True)


@pytest.mark.parametrize(
    "field,value",
    [
        ("checkpoint", "arbitrary/model"),
        ("checkpoint_revision", REVISION),
        ("provider_package_version", PACKAGE_VERSION),
        ("adapter_version", ADAPTER_VERSION),
    ],
)
def test_browser_cannot_choose_chronos_identity(field, value):
    _, policy, _, _ = build_fixture()
    request = dict(
        source_id=uuid4(),
        data_cutoff_date="2026-09-28",
        history_start_date="2026-07-01",
        snapshot_as_of="2026-10-01T00:00:00Z",
        policy=policy.model_dump() | {"strategy": "CHRONOS2", field: value},
    )
    with pytest.raises(ValidationError):
        ForecastRequest(**request)


def test_server_pin_and_profile_are_frozen_before_worker_validation(monkeypatch):
    validated = REGISTRATION.handler.validate_input(payload(monkeypatch))
    p = validated["forecast_input"]["policy"]
    assert p["adapter_version"] == ADAPTER_VERSION and p["checkpoint_revision"] == REVISION
    bad = copy.deepcopy(validated)
    bad["forecast_input"]["policy"]["adapter_version"] = "core-v1"
    with pytest.raises(ValueError):
        REGISTRATION.handler.validate_input(bad)
    with pytest.raises(ValueError):
        BASELINE.handler.validate_input(validated)


def test_disabled_model_registration_stays_readable_but_not_advertised(monkeypatch):
    monkeypatch.delenv("PP_CHRONOS_ENABLED", raising=False)
    registry = load_registry("production")
    assert registry.get(CHRONOS_CONTRACT) is REGISTRATION
    assert CHRONOS_CONTRACT not in registry.execution_advertisement()[0]


@pytest.mark.parametrize("content", ["[]", "null", "{", '{"chronos_config": []}'])
def test_corrupt_cached_config_disables_only_model_capability(monkeypatch, tmp_path, content):
    enable(monkeypatch)
    monkeypatch.setenv("PP_CHRONOS_MODEL_CACHE", str(tmp_path))
    monkeypatch.setattr(chronos_runtime, "version", lambda _name: PACKAGE_VERSION)
    monkeypatch.setattr(chronos_runtime.importlib.util, "find_spec", lambda _name: object())
    snapshot = tmp_path / "models--amazon--chronos-2" / "snapshots" / REVISION
    snapshot.mkdir(parents=True)
    (snapshot / "model.safetensors").write_bytes(b"sample")
    (snapshot / "config.json").write_text(content)
    assert chronos_runtime.execution_capability() is None
    assert "forecast.v1" in load_registry("production").execution_advertisement()[0]


def test_live_advertisement_has_exact_profile(monkeypatch):
    data = payload(monkeypatch)
    required = REGISTRATION.handler.required_capability(data)
    monkeypatch.setattr(REGISTRATION.handler, "execution_capability", lambda: required)
    contracts, profiles = load_registry("production").execution_advertisement()
    assert CHRONOS_CONTRACT in contracts and profiles[CHRONOS_CONTRACT] == required


@pytest.mark.parametrize("mismatch", [None, "revision", "malformed"])
def test_admission_rejects_missing_wrong_or_malformed_worker_model_profile(monkeypatch, mismatch):
    data = payload(monkeypatch)
    profile = policy_capability(ForecastInput.model_validate(data["forecast_input"]).policy)
    advertised = copy.deepcopy(profile)
    if mismatch == "revision":
        advertised["checkpoint_revision"] = "b" * 40
    limits = supervisor_advertisement(
        PRODUCTION_PROFILE,
        handler_contracts=[CHRONOS_CONTRACT],
        process_containment=True,
    )
    if mismatch is not None:
        limits["capabilities"]["handler_profiles"] = (
            {CHRONOS_CONTRACT: advertised} if mismatch != "malformed" else []
        )
    now = datetime.now(UTC)
    ctl = dict(heartbeat_at=now, state="READY", recovery_required=False, effective_limits=limits)
    queue = QueueRepository(None, registry=load_registry("production"), profile=PRODUCTION_PROFILE)
    assert (
        queue._admission(
            SimpleNamespace(scalar=lambda *_a, **_k: 0), ctl, now, CHRONOS_CONTRACT, data
        )
        == AdmissionOutcome.COMPUTE_UNAVAILABLE
    )
    limits["capabilities"]["handler_profiles"] = {CHRONOS_CONTRACT: profile}
    assert (
        queue._admission(
            SimpleNamespace(scalar=lambda *_a, **_k: 0), ctl, now, CHRONOS_CONTRACT, data
        )
        == AdmissionOutcome.ACCEPT
    )


def test_no_fallback_publishes_honest_incomplete_quantile_result(monkeypatch):
    data = payload(monkeypatch)
    monkeypatch.setattr(REGISTRATION.handler, "primary_adapter", lambda _inputs: Model())
    result = REGISTRATION.handler.execute_step("primary", data, (), context())
    saved = REGISTRATION.publisher.validate(
        data,
        [
            StepOutcome(
                "primary",
                StepStatus.COMPLETED,
                output=result,
            )
        ],
    )["forecast_output"]
    assert not saved["ready_for_publication"]
    assert saved["actual_providers"] == ["CHRONOS2"]
    assert sum(s["status"] == "AVAILABLE" for s in saved["series"]) == 12
    assert sum(len(s["points"]) for s in saved["series"]) == 84
    assert all(
        s["actual_provider"]["checkpoint_revision"] == REVISION
        for s in saved["series"]
        if s["status"] == "AVAILABLE"
    )


def test_whole_batch_fallback_is_baseline_provenance(monkeypatch):
    data = payload(monkeypatch, fallback=True)
    monkeypatch.setattr(REGISTRATION.handler, "primary_adapter", lambda _inputs: Model())
    with pytest.raises(ClassifiedStepFailure):
        REGISTRATION.handler.execute_step("primary", data, (), context())
    failed = StepOutcome(
        "primary",
        StepStatus.FAILED,
        error_code="PRIMARY_SERIES_UNAVAILABLE",
        fallback_eligible=True,
    )
    result = REGISTRATION.handler.execute_step("fallback", data, [failed.summary()], context())
    saved = REGISTRATION.publisher.validate(
        data,
        [
            failed,
            StepOutcome(
                "fallback",
                StepStatus.COMPLETED,
                output=result,
            ),
        ],
    )["forecast_output"]
    assert saved["ready_for_publication"] and saved["actual_providers"] == ["MOVING_AVERAGE"]
    assert all(
        s["fallback_used"]
        and s["actual_provider"]["name"] == "MOVING_AVERAGE"
        and s["actual_provider"]["checkpoint"] is None
        for s in saved["series"]
    )
    assert all(
        p["interval_method"] == "NONE" and p["estimate_kind"] == "MEAN"
        for s in saved["series"]
        for p in s["points"]
    )


def test_publisher_rejects_wrong_checkpoint_and_quantile_claims(monkeypatch):
    data = payload(monkeypatch)
    monkeypatch.setattr(REGISTRATION.handler, "primary_adapter", lambda _inputs: Model())
    result = REGISTRATION.handler.execute_step("primary", data, (), context())
    for row in result["forecast_output"]["series"]:
        if row["actual_provider"]:
            row["actual_provider"]["checkpoint_revision"] = "b" * 40
    with pytest.raises(PublicationRejected):
        REGISTRATION.publisher.validate(
            data, [StepOutcome("primary", StepStatus.COMPLETED, output=result)]
        )


def test_programming_errors_do_not_enable_fallback(monkeypatch):
    data = payload(monkeypatch, fallback=True)

    class Bug(Model):
        def predict(self, *_args):
            raise RuntimeError("defect")

    monkeypatch.setattr(REGISTRATION.handler, "primary_adapter", lambda _inputs: Bug())
    with pytest.raises(RuntimeError, match="defect"):
        REGISTRATION.handler.execute_step("primary", data, (), context())


def test_publish_boundary_rejects_staged_wrong_model_before_inserts(monkeypatch):
    data = payload(monkeypatch)
    inputs = ForecastInput.model_validate(data["forecast_input"])
    monkeypatch.setattr(REGISTRATION.handler, "primary_adapter", lambda _inputs: Model())
    ctx = context()
    result = REGISTRATION.handler.execute_step("primary", data, (), ctx)
    for row in result["forecast_output"]["series"]:
        if row["actual_provider"]:
            row["actual_provider"]["checkpoint_revision"] = "b" * 40
    calls = []

    def execute(statement):
        calls.append(statement)
        return SimpleNamespace(
            mappings=lambda: SimpleNamespace(
                one=lambda: {
                    "input_package": {"input": data},
                }
            )
        )

    identity = PublicationIdentity(
        ctx.job_id,
        ctx.attempt_id,
        inputs.organization_id,
        CHRONOS_CONTRACT,
        "not-used-by-publisher",
    )
    with pytest.raises(PublicationRejected):
        REGISTRATION.publisher.publish(SimpleNamespace(execute=execute), identity, result)
    assert len(calls) == 1  # frozen-job read only; no result row was inserted


@pytest.mark.parametrize("limits", [None, {}, {"version": 2, "capabilities": []}])
def test_malformed_advertisement_fails_closed_without_attribute_error(monkeypatch, limits):
    data = payload(monkeypatch)
    now = datetime.now(UTC)
    ctl = dict(heartbeat_at=now, state="READY", recovery_required=False, effective_limits=limits)
    queue = QueueRepository(None, registry=load_registry("production"), profile=PRODUCTION_PROFILE)
    outcome = queue._admission(
        SimpleNamespace(scalar=lambda *_a, **_k: 0), ctl, now, CHRONOS_CONTRACT, data
    )
    assert outcome == AdmissionOutcome.COMPUTE_UNAVAILABLE


def test_chronos_retains_original_step_deadlines(monkeypatch):
    steps = REGISTRATION.handler.steps(payload(monkeypatch, fallback=True), PRODUCTION_PROFILE)
    assert [s.name for s in steps] == ["primary", "fallback"]
    assert steps[0].cutoff_s == 270 and PRODUCTION_PROFILE.forecast_total_s == 300
    no_fallback = REGISTRATION.handler.steps(payload(monkeypatch), PRODUCTION_PROFILE)
    assert len(no_fallback) == 1 and no_fallback[0].cutoff_s == 270


def test_child_env_carries_only_trusted_model_configuration(monkeypatch):
    enable(monkeypatch)
    monkeypatch.setenv("DATABASE_URL", "must-not-escape")
    monkeypatch.setenv("PP_TEST_DATABASE_URL", "must-not-escape")
    monkeypatch.setenv("HF_TOKEN", "must-not-escape")
    env = PosixProcessDriver(cwd=Path(__file__).parents[2])._child_env("test-nonce")
    assert env["PP_CHRONOS_REVISION"] == REVISION
    assert env["PP_CHRONOS_MODEL_CACHE"] == "/operator/cache"
    assert not {"DATABASE_URL", "PP_TEST_DATABASE_URL", "HF_TOKEN"}.intersection(env)
