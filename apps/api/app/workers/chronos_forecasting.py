"""Opt-in Chronos contract; baseline admission/history needs no model dependency."""

from app.services.chronos_runtime import (
    CHRONOS_CONTRACT,
    execution_capability,
    operator_config,
)
from app.services.forecasting.adapters.chronos2 import (
    ADAPTER_VERSION,
    MODEL_ID,
    PACKAGE_VERSION,
    Chronos2Adapter,
    ChronosConfig,
)
from app.services.jobs.contracts import OperationKind, StepSpec
from app.services.jobs.registry import Registration
from app.workers.forecasting import ForecastHandler, ForecastPublisher


def validate_chronos_policy(policy):
    if (
        policy.strategy != "CHRONOS2"
        or policy.adapter_version != ADAPTER_VERSION
        or policy.checkpoint != MODEL_ID
        or policy.provider_package_version != PACKAGE_VERSION
    ):
        raise ValueError("Invalid frozen Chronos execution profile")
    return ChronosConfig(policy.checkpoint_revision)


class ChronosHandler(ForecastHandler):
    def validate_policy(self, inputs):
        validate_chronos_policy(inputs.policy)

    def steps(self, validated, profile):
        steps = super().steps(validated, profile)
        if not validated["forecast_input"]["policy"]["allow_fallback"]:
            return (
                StepSpec(
                    name="primary",
                    min_s=profile.method_min_s,
                    cutoff_s=profile.forecast_primary_cutoff_s,
                ),
            )
        return steps

    def primary_adapter(self, inputs):
        from app.services.forecasting.adapters.base import ProviderError

        approved = operator_config()
        if approved is None or approved.revision != inputs.policy.checkpoint_revision:
            # An operator change cannot cause an old queued job to run a new pin.
            raise ProviderError("PROVIDER_UNAVAILABLE", "Frozen Chronos profile is unavailable")
        return Chronos2Adapter(approved)

    def execute_step(self, step, validated, prior, context):
        # Provider construction itself can be unavailable before pure forecast().
        from app.services.forecasting.adapters.base import ProviderError
        from app.services.jobs.registry import ClassifiedStepFailure

        try:
            return super().execute_step(step, validated, prior, context)
        except ProviderError as exc:
            raise ClassifiedStepFailure(exc.code) from exc

    @staticmethod
    def execution_capability():
        return execution_capability()

    @staticmethod
    def required_capability(validated):
        return {
            key: validated["forecast_input"]["policy"][field]
            for key, field in {
                "checkpoint": "checkpoint",
                "checkpoint_revision": "checkpoint_revision",
                "package_version": "provider_package_version",
                "adapter_version": "adapter_version",
            }.items()
        }


class ChronosPublisher(ForecastPublisher):
    contract = CHRONOS_CONTRACT

    def primary_identity(self, inputs):
        return validate_chronos_policy(inputs.policy).identity


REGISTRATION = Registration(
    contract=CHRONOS_CONTRACT,
    operation_kind=OperationKind.FORECAST,
    input_schema_version="1",
    max_input_bytes=16_000_000,
    max_output_bytes=4_000_000,
    handler=ChronosHandler(),
    publisher=ChronosPublisher(),
)
