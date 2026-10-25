"""Production baseline forecast handler and atomic publisher for the shared lane."""

from collections.abc import Mapping
from uuid import uuid4

import sqlalchemy as sa

from app.models.forecasts import ForecastPointRecord, ForecastRun, ForecastSeries
from app.schemas.forecast_api import BaselinePolicy
from app.services.forecasting.adapters.moving_average import MovingAverageAdapter
from app.services.forecasting.adapters.seasonal_naive import SeasonalNaiveAdapter
from app.services.forecasting.postprocessing import validate_output
from app.services.forecasting.preparation import validate_input
from app.services.forecasting.schemas import ForecastInput, ForecastOutput
from app.services.forecasting.service import forecast
from app.services.jobs.contracts import OperationKind, StepStatus
from app.services.jobs.policies import forecast_steps
from app.services.jobs.registry import (
    ClassifiedStepFailure,
    InputRejected,
    PublicationRejected,
    Registration,
)


class ForecastHandler:
    def validate_policy(self, inputs):
        BaselinePolicy.model_validate(inputs.policy.model_dump())

    def primary_adapter(self, inputs):
        return (
            SeasonalNaiveAdapter()
            if inputs.policy.strategy == "SEASONAL_NAIVE"
            else MovingAverageAdapter()
        )

    def validate_input(self, payload):
        if not isinstance(payload, Mapping) or set(payload) != {"forecast_input"}:
            raise InputRejected("INVALID_INPUT", "Unknown forecast payload")
        try:
            inputs = validate_input(ForecastInput.model_validate(payload["forecast_input"]))
            self.validate_policy(inputs)
            if len(inputs.series) > 800 or sum(len(s.observations) for s in inputs.series) > 60_000:
                raise ValueError("History exceeds worker bounds")
        except (ValueError, TypeError, AttributeError) as exc:
            raise InputRejected("INVALID_FORECAST_INPUT", "Invalid frozen forecast input") from exc
        return {
            "forecast_input": inputs.model_dump(mode="json"),
        }

    def steps(self, validated, profile):
        policy = validated["forecast_input"]["policy"]
        return forecast_steps(
            profile,
            fallback_allowed=policy["allow_fallback"] and policy["strategy"] != "MOVING_AVERAGE",
        )

    def execute_step(self, step, validated, prior, context):
        inputs = validate_input(ForecastInput.model_validate(validated["forecast_input"]))
        if step not in {"primary", "fallback"}:
            raise ValueError("Unknown forecast step")
        if step == "fallback" and (
            not inputs.policy.allow_fallback
            or not prior
            or prior[-1].get("fallback_eligible") is not True
        ):
            raise ValueError("Fallback requires explicit opt-in and a classified failure")
        # The supervisor owns the primary/fallback boundary and their shared deadline.
        adapter = self.primary_adapter(inputs) if step == "primary" else MovingAverageAdapter()
        output = forecast(inputs, adapter=adapter, run_id=context.job_id, single_candidate=True)
        if (
            step == "primary"
            and inputs.policy.allow_fallback
            and (inputs.policy.strategy != "MOVING_AVERAGE")
            and any(row.status != "AVAILABLE" for row in output.series)
        ):
            # Only the pure service's classified DATA/PROVIDER failures arrive here.
            # A programming exception escapes this function and cannot enable fallback.
            raise ClassifiedStepFailure("PRIMARY_SERIES_UNAVAILABLE")
        if step == "fallback":
            if not prior or prior[-1].get("fallback_eligible") is not True:
                raise ValueError("Fallback requires a classified failure or supervised timeout")
            reason = prior[-1].get("error_code") or "PRIMARY_SERIES_UNAVAILABLE"
            output = output.model_copy(
                update={
                    "warnings": tuple(
                        sorted(set(output.warnings) | {"WHOLE_BATCH_BASELINE_FALLBACK"})
                    ),
                    "series": tuple(
                        row.model_copy(
                            update={
                                "fallback_used": True,
                                "fallback_reason": reason,
                                "warnings": tuple(
                                    sorted(set(row.warnings) | {"WHOLE_BATCH_BASELINE_FALLBACK"})
                                ),
                            }
                        )
                        if row.status == "AVAILABLE"
                        else row
                        for row in output.series
                    ),
                }
            )
        return {"forecast_output": output.model_dump(mode="json")}


class ForecastPublisher:
    contract = "forecast.v1"

    def primary_identity(self, inputs):
        BaselinePolicy.model_validate(inputs.policy.model_dump())
        return (
            MovingAverageAdapter.identity
            if inputs.policy.strategy == "MOVING_AVERAGE"
            else SeasonalNaiveAdapter.identity
        )

    @staticmethod
    def validate_series(row, expected, fallback):
        if row.actual_provider != expected or row.fallback_used != fallback:
            raise ValueError("Provider provenance contradicts execution")
        for point in row.points:
            if expected.name == "CHRONOS2":
                if (
                    point.interval_method != "MODEL_QUANTILES"
                    or point.estimate_kind != "MEDIAN"
                    or any(v is None for v in (point.p10, point.p50, point.p90))
                ):
                    raise ValueError("Chronos must retain actual model quantiles")
            elif point.interval_method != "NONE" or point.estimate_kind != (
                "MEAN" if expected.name == "MOVING_AVERAGE" else "POINT"
            ):
                raise ValueError("Baseline outputs cannot claim model quantiles")

    def validate(self, validated, outcomes):
        try:
            inputs = validate_input(ForecastInput.model_validate(validated["forecast_input"]))
            completed = [o for o in outcomes if o.status == StepStatus.COMPLETED]
            if not completed:
                last = outcomes[-1] if outcomes else None
                raise PublicationRejected(
                    last.error_code if last and last.error_code else "HANDLER_FAILED",
                    timed_out=bool(last and last.status == StepStatus.TIMED_OUT),
                )
            output = validate_output(
                inputs, ForecastOutput.model_validate(completed[-1].output["forecast_output"])
            )
            final = completed[-1]
            fallback = final.name == "fallback"
            if final.name not in {"primary", "fallback"} or (
                fallback
                and (
                    not inputs.policy.allow_fallback
                    or len(outcomes) < 2
                    or not outcomes[-2].fallback_eligible
                )
            ):
                raise ValueError("Invalid execution path")
            expected = MovingAverageAdapter.identity if fallback else self.primary_identity(inputs)
            for row in output.series:
                if row.status != "AVAILABLE":
                    continue
                self.validate_series(row, expected, fallback)
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            raise PublicationRejected("OUTPUT_INVALID") from exc
        return {"forecast_output": output.model_dump(mode="json")}

    def publish(self, connection, identity, package):
        """Called INSIDE QueueRepository.publish's fence/transaction, never standalone."""
        from app.models.jobs import compute_jobs

        job = (
            connection.execute(
                sa.select(compute_jobs).where(
                    compute_jobs.c.job_id == identity.job_id,
                    compute_jobs.c.organization_id == identity.organization_id,
                )
            )
            .mappings()
            .one()
        )
        inputs = validate_input(
            ForecastInput.model_validate(job["input_package"]["input"]["forecast_input"])
        )
        try:
            output = validate_output(
                inputs, ForecastOutput.model_validate(package["forecast_output"])
            )
            if (
                output.run_id != identity.job_id
                or inputs.organization_id != identity.organization_id
                or identity.handler_contract != self.contract
            ):
                raise ValueError("Publication ownership mismatch")
            primary = self.primary_identity(inputs)
            available = [row for row in output.series if row.status == "AVAILABLE"]
            if len({row.fallback_used for row in available}) > 1:
                raise ValueError("Publication requires whole-batch provider provenance")
            for row in available:
                if row.fallback_used and not inputs.policy.allow_fallback:
                    raise ValueError("Fallback was not authorized")
                self.validate_series(
                    row,
                    MovingAverageAdapter.identity if row.fallback_used else primary,
                    row.fallback_used,
                )
        except (ValueError, TypeError, KeyError) as exc:
            raise PublicationRejected("OUTPUT_INVALID") from exc
        own = {"organization_id": identity.organization_id}
        connection.execute(
            sa.insert(ForecastRun).values(
                **own,
                id=output.run_id,
                job_id=identity.job_id,
                attempt_id=identity.attempt_id,
                input_hash=inputs.input_hash,
                planning_ready=output.ready_for_publication,
                frozen_input=inputs.model_dump(mode="json"),
                output=output.model_dump(mode="json"),
            )
        )
        for series in output.series:
            connection.execute(
                sa.insert(ForecastSeries).values(
                    **own,
                    id=series.result_id,
                    run_id=output.run_id,
                    site_id=series.scope.key.site_id,
                    product_id=series.scope.key.product_id,
                    target_type=series.scope.key.target_type,
                    status=series.status,
                    details=series.model_dump(mode="json", exclude={"points"}),
                )
            )
            if series.points:
                connection.execute(
                    sa.insert(ForecastPointRecord),
                    [
                        dict(
                            **own,
                            id=uuid4(),
                            series_id=series.result_id,
                            day=p.day,
                            central_estimate=p.central_estimate,
                            details=p.model_dump(mode="json"),
                        )
                        for p in series.points
                    ],
                )
        return {
            "result_ref": str(output.run_id),
            "planning_ready": output.ready_for_publication,
            "input_hash": inputs.input_hash,
        }


REGISTRATION = Registration(
    contract="forecast.v1",
    operation_kind=OperationKind.FORECAST,
    input_schema_version="1",
    max_input_bytes=16_000_000,
    max_output_bytes=4_000_000,
    handler=ForecastHandler(),
    publisher=ForecastPublisher(),
)
