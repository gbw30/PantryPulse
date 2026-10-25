"""Allowlisted handler/publisher interfaces (WQ-01).

A payload selects only a registered contract/version. It can never name an import path,
shell command, pickle or callback. Registrations carry explicit serialized-size bounds; no
production default is inferred.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID

from app.services.jobs.contracts import OperationKind, RuntimeProfile, StepOutcome, StepSpec


class InputRejected(ValueError):
    """Typed input validation failed before admission; no job is accepted."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class UnregisteredContract(LookupError):
    pass


class ClassifiedStepFailure(Exception):
    """A handler-classified step failure (for example a provider failure).

    Only classified failures may make a following fallback step eligible; any other
    exception is a programming/input error that fallback must not hide.
    """

    def __init__(self, code: str, *, fallback_eligible: bool = True):
        super().__init__(code)
        self.code = code
        self.fallback_eligible = fallback_eligible


class PublicationRejected(Exception):
    """The publisher found the staged outcome invalid or unpublishable."""

    def __init__(self, code: str, *, timed_out: bool = False):
        super().__init__(code)
        self.code = code
        self.timed_out = timed_out


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    job_id: UUID
    attempt_id: UUID
    step: str
    remaining_s: float
    search_limit_s: float


@dataclass(frozen=True, slots=True)
class PublicationIdentity:
    job_id: UUID
    attempt_id: UUID
    organization_id: UUID
    handler_contract: str
    input_sha256: str


class Handler(Protocol):
    def validate_input(self, payload: Mapping[str, Any]) -> dict[str, Any]: ...

    def steps(
        self, validated: Mapping[str, Any], profile: RuntimeProfile
    ) -> tuple[StepSpec, ...]: ...

    def execute_step(
        self,
        step: str,
        validated: Mapping[str, Any],
        prior: Sequence[Mapping[str, Any]],
        context: ExecutionContext,
    ) -> dict[str, Any]: ...


class Publisher(Protocol):
    def validate(
        self, validated: Mapping[str, Any], outcomes: Sequence[StepOutcome]
    ) -> dict[str, Any]: ...

    def publish(
        self, connection: Any, identity: PublicationIdentity, package: Mapping[str, Any]
    ) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class Registration:
    contract: str
    operation_kind: OperationKind
    input_schema_version: str
    max_input_bytes: int
    max_output_bytes: int
    handler: Handler
    publisher: Publisher

    def execution_budget(self, validated: Mapping[str, Any], profile: RuntimeProfile) -> float:
        """A registered handler may freeze a shorter allowance than the lane ceiling."""
        import math

        from app.services.jobs.policies import operation_budget_s

        ceiling = operation_budget_s(self.operation_kind, profile)
        callback = getattr(self.handler, "execution_budget", None)
        budget = callback(validated, profile) if callback else ceiling
        if isinstance(budget, bool) or not isinstance(budget, int | float) or (
            not math.isfinite(budget) or not profile.publication_reserve_s < budget <= ceiling
        ):
            raise InputRejected("UNSUPPORTED_EXECUTION_SETTINGS", "Budget exceeds lane capability")
        return budget

    def __post_init__(self) -> None:
        if not self.contract or not self.input_schema_version:
            raise ValueError("contract and input schema version are required")
        for name in ("max_input_bytes", "max_output_bytes"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{name} must be a positive int")
        OperationKind(self.operation_kind)


class Registry:
    def __init__(self, registrations: Sequence[Registration] = ()):
        by_contract: dict[str, Registration] = {}
        for reg in registrations:
            if reg.contract in by_contract:
                raise ValueError(f"duplicate handler contract {reg.contract!r}")
            by_contract[reg.contract] = reg
        self._by_contract = by_contract

    def get(self, contract: str) -> Registration:
        try:
            return self._by_contract[contract]
        except (KeyError, TypeError):
            raise UnregisteredContract(f"handler contract {contract!r} is not registered") from None

    def contracts(self) -> tuple[str, ...]:
        return tuple(sorted(self._by_contract))
