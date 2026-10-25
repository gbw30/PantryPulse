"""Allowlisted real OR steps, isolated by the shared process driver."""

from app.schemas.or_execution import ORExecutionInput
from app.services.jobs.contracts import OperationKind, StepSpec
from app.services.jobs.registry import InputRejected, Registration, Registry
from app.services.optimization.scenario import verify_scenario


class ORHandler:
    def __init__(self, comparison):
        self.comparison = comparison

    def validate_input(self, payload):
        try:
            value = ORExecutionInput.model_validate(dict(payload))
            verify_scenario(value.scenario)
            if self.comparison == (value.method is not None):
                raise ValueError("METHOD_ENVELOPE_MISMATCH")
            if value.scenario.policy.purpose != "PRIMARY":
                raise ValueError("PRIMARY_POLICY_REQUIRED")
            from app.services.optimization.service import DEFAULT_SETTINGS

            settings = value.settings
            if (
                set(settings) != set(DEFAULT_SETTINGS)
                or settings["version"] != DEFAULT_SETTINGS["version"]
                or type(settings["workers"]) is not int
                or settings["workers"] != 1
                or type(settings["seed"]) is not int
                or not 0 <= settings["seed"] < 2**31
                or type(settings["search_milliseconds"]) is not int
                or not 0 < settings["search_milliseconds"] <= 15000
            ):
                raise ValueError("UNSUPPORTED_SOLVER_SETTINGS")
            return value.model_dump(mode="json")
        except (ValueError, TypeError) as exc:
            raise InputRejected("OR_INPUT_INVALID", "Invalid immutable OR execution input") from exc

    def steps(self, validated, profile):
        methods = ("CLASSICAL_GP", "EGP_PI_INSPIRED") if self.comparison else (validated["method"],)
        return tuple(
            StepSpec(name=m, min_s=profile.method_min_s, max_s=profile.method_wall_s)
            for m in methods
        )

    def execute_step(self, step, validated, prior, context):
        # OR-DEC-011 [PROVISIONAL]: child computes only; parent checks/publishes.
        from app.services.optimization.service import solve_one

        value = ORExecutionInput.model_validate(validated)
        settings = dict(value.settings)
        settings["search_milliseconds"] = max(
            1,
            min(
                settings["search_milliseconds"],
                int(context.search_limit_s * 1000),
                int((context.remaining_s - 2) * 1000),
            ),
        )
        return solve_one(value.scenario, step, settings).model_dump(mode="json")


def registrations():
    from app.workers.or_publication import ORPublisher

    return tuple(
        Registration(
            contract=contract,
            operation_kind=kind,
            input_schema_version="or-execution-v1",
            max_input_bytes=4 * 1024**2,
            max_output_bytes=8 * 1024**2,
            handler=ORHandler(comparison),
            publisher=ORPublisher(comparison),
        )
        for contract, kind, comparison in (
            ("or-allocation-v1", OperationKind.ALLOCATION, False),
            ("or-comparison-v1", OperationKind.COMPARISON, True),
        )
    )


def production_registry():
    return Registry(registrations())
