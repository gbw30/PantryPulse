"""Allowlisted handler/publisher interfaces (WQ-01).

A payload selects only a registered contract/version. It can never name an import path,
shell command, pickle or callback. Registrations carry explicit serialized-size bounds; no
production default is inferred.
"""

import re
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

    # Optional hooks (CR-w1-data-2), looked up with getattr like `execution_budget`:
    #
    # prepare(engine, identity, package, *, remaining_s) -> package
    #     Runs in the supervisor after `validate` and before `publish`, outside the queue
    #     lock, once per attempt. It may do slow database work (bulk loads) in its own
    #     transactions, finishing within `remaining_s`; its result is the package passed
    #     to `publish`. Raise PublicationRejected to fail the attempt.
    # discard(engine, identity) -> None
    #     Undoes `prepare` when the attempt ends without a committed publication (rejected,
    #     timed out, cancelled, fenced, ownership lost, commit lost, or finalized elsewhere).
    #     Never called after a committed publication. Best effort: it must be idempotent,
    #     and a supervisor crash between prepare and publish can leave data that a later
    #     prepare must tolerate or clean.
    # follow_ups(connection, identity, manifest) -> Sequence[FollowUp]   (CR-w1-data-5)
    #     Runs right after `publish`, in the same locked transaction (`connection` is that
    #     transaction: read only what the follow-up needs, briefly). Each FollowUp is
    #     admitted there as a new job with the parent's organization and actor, so it exists
    #     only if the publication commits. A rejected follow-up (unknown contract, invalid
    #     input, queue full, compute unavailable) never fails the publication: it is rolled
    #     back alone and audited as FOLLOW_UP_REJECTED with the reason code.


@dataclass(frozen=True, slots=True)
class FollowUp:
    """A job a publisher queues together with its committed result (Publisher.follow_ups)."""

    contract: str
    payload: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class Registration:
    contract: str
    operation_kind: OperationKind
    input_schema_version: str
    max_input_bytes: int
    max_output_bytes: int
    handler: Handler
    publisher: Publisher
    # Named local_secrets rows passed only to this contract's step children, as
    # secret_env(name) variables; never in the payload, logs or job rows (W1-D08).
    child_secrets: tuple[str, ...] = ()

    def execution_budget(self, validated: Mapping[str, Any], profile: RuntimeProfile) -> float:
        """A registered handler may freeze a shorter allowance than the lane ceiling."""
        import math

        from app.services.jobs.policies import operation_budget_s

        ceiling = operation_budget_s(self.operation_kind, profile)
        callback = getattr(self.handler, "execution_budget", None)
        budget = callback(validated, profile) if callback else ceiling
        if (
            isinstance(budget, bool)
            or not isinstance(budget, int | float)
            or (not math.isfinite(budget) or not profile.publication_reserve_s < budget <= ceiling)
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
        for name in self.child_secrets:
            if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_]*", name):
                raise ValueError(f"invalid child secret name {name!r}")


def secret_env(name: str) -> str:
    """The step child's environment variable for a declared secret."""
    return "PP_SECRET_" + name.upper()


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

    def execution_advertisement(self) -> tuple[tuple[str, ...], dict[str, Any]]:
        """Only executable opt-in handlers are advertised by an actual supervisor.

        Registration remains unconditional for API validation and saved reads.
        Existing handlers without a preflight hook retain their old behavior.
        """
        contracts, profiles = [], {}
        for contract in self.contracts():
            hook = getattr(self.get(contract).handler, "execution_capability", None)
            if hook is None:
                contracts.append(contract)
            else:
                profile = hook()
                if profile is not None:
                    contracts.append(contract)
                    profiles[contract] = profile
        return tuple(contracts), profiles
