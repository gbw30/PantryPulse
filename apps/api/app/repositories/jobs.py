"""Transactional PostgreSQL queue repository (WQ-02, WQ-05).

Every mutation locks the lane's ``compute_control`` row first (lock order control -> job ->
attempt -> command/result) and keeps the transaction short: no transaction is held across
child execution, waiting or model/solver work. Database ``clock_timestamp()`` read after the
lock is the persisted clock. Reads acquire no mutation locks and never change state.
"""

import re
import uuid
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import sqlalchemy as sa
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DataError, DBAPIError, InterfaceError, OperationalError

from app.services.jobs.contracts import (
    LANE_OCCUPYING_STATES,
    AdmissionOutcome,
    AttemptState,
    CommandAction,
    HeartbeatStatus,
    OperationKind,
    ReasonCode,
    RuntimeProfile,
    SupervisorState,
    canonical_json,
    sha256_hex,
)
from app.services.jobs.policies import (
    admission_outcome,
    advertised_capability,
    can_retry,
    final_state_for_stop_reason,
    heartbeat_status,
    operation_budget_s,
)
from app.services.jobs.registry import (
    InputRejected,
    PublicationIdentity,
    PublicationRejected,
    Registry,
    UnregisteredContract,
)

IDEMPOTENCY_KEY = re.compile(r"[A-Za-z0-9._:-]{1,128}")
_SCHEMA_NAME = re.compile(r"[a-z_][a-z0-9_]{0,62}")
_OCCUPYING = tuple(s.value for s in LANE_OCCUPYING_STATES)


def create_queue_engine(url: str, *, schema: str | None = None, pool_size: int = 10) -> sa.Engine:
    parsed = make_url(url)
    if parsed.get_backend_name() not in ("postgres", "postgresql"):
        raise ValueError("PostgreSQL is required")
    connect_args: dict[str, Any] = {"connect_timeout": 15}
    if schema is not None:
        if not _SCHEMA_NAME.fullmatch(schema):
            raise ValueError("schema must be a simple lowercase identifier")
    engine = sa.create_engine(
        parsed.set(drivername="postgresql+psycopg"),
        pool_pre_ping=True, pool_size=pool_size, max_overflow=10, connect_args=connect_args,
        hide_parameters=True,
    )
    if schema is not None:
        @sa.event.listens_for(engine, "begin")
        def select_schema(connection):
            # PgBouncer rejects startup options for search_path. SET LOCAL selects
            # the validated schema for THIS transaction and cannot leak to the next
            # borrower of a pooled server connection.
            connection.exec_driver_sql(f'SET LOCAL search_path TO "{schema}"')
    return engine


# --- errors -------------------------------------------------------------------------------


class QueueError(Exception):
    code = "QUEUE_ERROR"

    def __init__(self, message: str = "", *, code: str | None = None):
        if code is not None:
            self.code = code
        super().__init__(message or self.code)


class AdmissionRejected(QueueError):
    """503: COMPUTE_UNAVAILABLE or COMPUTE_QUEUE_FULL. No job was accepted."""


class IdempotencyConflict(QueueError):
    code = "IDEMPOTENCY_CONFLICT"


class JobStateConflict(QueueError):
    code = "JOB_STATE_CONFLICT"


class JobNotFound(QueueError):
    code = "NOT_FOUND"


class QueueStorageUnavailable(QueueError):
    code = "QUEUE_STORAGE_UNAVAILABLE"


class OwnershipLost(QueueError):
    code = "OWNERSHIP_LOST"


class Fenced(QueueError):
    """Publication authority was revoked: stale owner/token, stop requested or deadline."""

    code = "PUBLICATION_FENCED"


class CommitUncertain(QueueError):
    """COMMIT did not acknowledge; the outcome must be reconciled by identity."""

    code = "PUBLICATION_COMMIT_UNCERTAIN"


# --- records ------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class TrustedScope:
    """Trusted internal scope supplied by a backend adapter, never by the client."""

    organization_id: uuid.UUID
    actor_ref: str


@dataclass(frozen=True, slots=True)
class Accepted:
    job_id: uuid.UUID
    attempt_id: uuid.UUID
    state: AttemptState
    replayed: bool


@dataclass(frozen=True, slots=True)
class CancelResult:
    job_id: uuid.UUID
    attempt_id: uuid.UUID
    state: AttemptState
    completed: bool
    replayed: bool


@dataclass(frozen=True, slots=True)
class Ownership:
    lane_id: str
    supervisor_id: uuid.UUID
    generation: int


@dataclass(frozen=True, slots=True)
class ControlView:
    lane_id: str
    state: SupervisorState
    supervisor_id: uuid.UUID | None
    generation: int
    host_identity: str | None
    heartbeat_at: datetime | None
    active_attempt_id: uuid.UUID | None
    recovery_required: bool
    effective_limits: dict[str, Any]


@dataclass(frozen=True, slots=True)
class AttemptView:
    """Attempt read model. The execution token is deliberately not exposed."""

    attempt_id: uuid.UUID
    job_id: uuid.UUID
    attempt_number: int
    state: AttemptState
    reason_code: str | None
    state_version: int
    enqueued_at: datetime
    queue_deadline_at: datetime
    supervisor_id: uuid.UUID | None
    supervisor_generation: int | None
    started_at: datetime | None
    execution_deadline_at: datetime | None
    primary_deadline_at: datetime | None
    current_phase: str | None
    execution_boundary: dict[str, Any] | None
    stop_requested_at: datetime | None
    stop_reason: str | None
    cleanup_confirmed_at: datetime | None
    diagnostics: dict[str, Any]
    completed_at: datetime | None
    result_manifest: dict[str, Any] | None
    error: dict[str, Any] | None


_ATTEMPT_VIEW_COLUMNS = (
    "attempt_id, job_id, attempt_number, state, reason_code, state_version, enqueued_at,"
    " queue_deadline_at, supervisor_id, supervisor_generation, started_at,"
    " execution_deadline_at, primary_deadline_at, current_phase, execution_boundary,"
    " stop_requested_at, stop_reason, cleanup_confirmed_at, diagnostics, completed_at,"
    " result_manifest, error"
)


def _attempt_view(row: Mapping[str, Any]) -> AttemptView:
    data = {k: row[k] for k in AttemptView.__dataclass_fields__}
    data["state"] = AttemptState(row["state"])
    return AttemptView(**data)


@dataclass(frozen=True, slots=True)
class JobView:
    job_id: uuid.UUID
    organization_id: uuid.UUID
    operation_kind: OperationKind
    handler_contract: str
    input_sha256: str
    state: AttemptState
    current_attempt_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    attempts: tuple[AttemptView, ...]


@dataclass(frozen=True, slots=True)
class ClaimedAttempt:
    job_id: uuid.UUID
    attempt_id: uuid.UUID
    attempt_number: int
    organization_id: uuid.UUID
    contract: str
    operation_kind: OperationKind
    input_package: dict[str, Any]
    input_sha256: str
    execution_token: uuid.UUID
    supervisor_generation: int
    started_at: datetime
    execution_deadline_at: datetime
    primary_deadline_at: datetime | None
    budget_s: float


@dataclass(frozen=True, slots=True)
class RecoveryItem:
    attempt_id: uuid.UUID
    job_id: uuid.UUID
    state: AttemptState
    stop_reason: str | None
    execution_boundary: dict[str, Any] | None
    supervisor_id: uuid.UUID | None
    supervisor_generation: int | None


def _json(value: Any) -> str:
    return canonical_json(value)


def _seconds(delta: timedelta) -> float:
    return delta.total_seconds()


class QueueRepository:
    def __init__(
        self,
        engine: sa.Engine,
        *,
        registry: Registry,
        profile: RuntimeProfile,
        lane_id: str = "default",
        lock_timeout_ms: int = 5_000,
        statement_timeout_ms: int = 10_000,
    ):
        self.engine = engine
        self.registry = registry
        self.profile = profile
        self.lane_id = lane_id
        self._lock_timeout_ms = int(lock_timeout_ms)
        self._statement_timeout_ms = int(statement_timeout_ms)

    # --- transaction plumbing ------------------------------------------------------------

    @contextmanager
    def _tx(self, *, lock_timeout_ms: int | None = None) -> Iterator[sa.Connection]:
        try:
            with self.engine.connect() as conn:
                with conn.begin():
                    self._set_timeouts(
                        conn, lock_timeout_ms or self._lock_timeout_ms, self._statement_timeout_ms
                    )
                    yield conn
        except (OperationalError, InterfaceError) as exc:
            raise QueueStorageUnavailable("queue storage unavailable") from exc

    @contextmanager
    def _read(self) -> Iterator[sa.Connection]:
        """Lock-free read connection; driver failures surface as QueueStorageUnavailable."""
        try:
            with self.engine.connect() as conn:
                yield conn
        except (OperationalError, InterfaceError) as exc:
            raise QueueStorageUnavailable("queue storage unavailable") from exc

    @staticmethod
    def _jsonb_normalized(conn: sa.Connection, encoded: str) -> dict[str, Any]:
        try:
            with conn.begin_nested():
                return conn.scalar(sa.text("SELECT CAST(:p AS jsonb)"), {"p": encoded})
        except DataError:
            raise InputRejected(
                "INPUT_NOT_REPRESENTABLE", "input cannot be stored as JSONB"
            ) from None

    @staticmethod
    def _set_timeouts(conn: sa.Connection, lock_ms: int, statement_ms: int) -> None:
        conn.execute(sa.text(f"SET LOCAL lock_timeout = {max(1, int(lock_ms))}"))
        conn.execute(sa.text(f"SET LOCAL statement_timeout = {max(1, int(statement_ms))}"))

    def _commit(self, transaction: sa.RootTransaction) -> None:
        """Publication COMMIT; overridable by tests to simulate an unacknowledged commit."""
        transaction.commit()

    def _lock_control(self, conn: sa.Connection) -> tuple[Mapping[str, Any], datetime]:
        ctl = (
            conn.execute(
                sa.text("SELECT * FROM compute_control WHERE lane_id = :l FOR UPDATE"),
                {"l": self.lane_id},
            )
            .mappings()
            .one()
        )
        now = conn.scalar(sa.text("SELECT clock_timestamp()"))
        return ctl, now

    @staticmethod
    def _is_owner(ctl: Mapping[str, Any], own: Ownership) -> bool:
        return ctl["supervisor_id"] == own.supervisor_id and ctl["generation"] == own.generation

    def _require_owner(self, ctl: Mapping[str, Any], own: Ownership) -> None:
        if not self._is_owner(ctl, own) or ctl["state"] == SupervisorState.OFFLINE:
            raise OwnershipLost("lane ownership changed")

    def _audit(
        self,
        conn: sa.Connection,
        event_type: str,
        *,
        job_id: uuid.UUID | None = None,
        attempt_id: uuid.UUID | None = None,
        from_state: str | None = None,
        to_state: str | None = None,
        own: Ownership | None = None,
        reason_code: str | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        conn.execute(
            sa.text(
                "INSERT INTO compute_audit_events (lane_id, job_id, attempt_id, event_type,"
                " from_state, to_state, supervisor_id, supervisor_generation, reason_code,"
                " details) VALUES (:l, :j, :a, :e, :f, :t, :s, :g, :r, CAST(:d AS jsonb))"
            ),
            {
                "l": self.lane_id,
                "j": job_id,
                "a": attempt_id,
                "e": event_type,
                "f": from_state,
                "t": to_state,
                "s": own.supervisor_id if own else None,
                "g": own.generation if own else None,
                "r": reason_code,
                "d": _json(dict(details or {})),
            },
        )

    def _transition(
        self,
        conn: sa.Connection,
        attempt: Mapping[str, Any],
        target: AttemptState,
        now: datetime,
        *,
        reason: str | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> None:
        """Move an attempt and its job projection together; the DB guard checks the edge."""
        sets = ["state = :state", "state_version = state_version + 1"]
        params: dict[str, Any] = {"a": attempt["attempt_id"], "state": target.value, "now": now}
        if reason is not None:
            sets.append("reason_code = :reason")
            params["reason"] = reason
        if target not in (AttemptState.QUEUED, AttemptState.RUNNING, AttemptState.STOPPING):
            sets.append("completed_at = :now")
        for i, (column, value) in enumerate((extra or {}).items()):
            if column in ("diagnostics_merge",):
                sets.append(f"diagnostics = diagnostics || CAST(:x{i} AS jsonb)")
                params[f"x{i}"] = _json(value)
            elif column in ("error", "result_manifest", "execution_boundary"):
                sets.append(f"{column} = CAST(:x{i} AS jsonb)")
                params[f"x{i}"] = None if value is None else _json(value)
            else:
                sets.append(f"{column} = :x{i}")
                params[f"x{i}"] = value
        conn.execute(
            sa.text(f"UPDATE compute_attempts SET {', '.join(sets)} WHERE attempt_id = :a"), params
        )
        conn.execute(
            sa.text(
                "UPDATE compute_jobs SET state = :state, updated_at = :now"
                " WHERE job_id = :j AND current_attempt_id = :a"
            ),
            {"state": target.value, "now": now, "j": attempt["job_id"], "a": attempt["attempt_id"]},
        )

    def _release_slot(self, conn: sa.Connection, attempt_id: uuid.UUID, now: datetime) -> None:
        conn.execute(
            sa.text(
                "UPDATE compute_control SET active_attempt_id = NULL, updated_at = :now"
                " WHERE lane_id = :l AND active_attempt_id = :a"
            ),
            {"l": self.lane_id, "a": attempt_id, "now": now},
        )

    def _expire_overdue(self, conn: sa.Connection, now: datetime) -> int:
        rows = (
            conn.execute(
                sa.text(
                    "SELECT attempt_id, job_id, state FROM compute_attempts"
                    " WHERE lane_id = :l AND state = 'QUEUED' AND queue_deadline_at <= :now"
                    " ORDER BY enqueued_at, attempt_id FOR UPDATE"
                ),
                {"l": self.lane_id, "now": now},
            )
            .mappings()
            .all()
        )
        for row in rows:
            self._transition(
                conn, row, AttemptState.EXPIRED, now, reason=ReasonCode.QUEUE_DEADLINE_REACHED
            )
            self._audit(
                conn,
                "ATTEMPT_EXPIRED",
                job_id=row["job_id"],
                attempt_id=row["attempt_id"],
                from_state="QUEUED",
                to_state="EXPIRED",
                reason_code=ReasonCode.QUEUE_DEADLINE_REACHED,
            )
        return len(rows)

    def _admission(
        self, conn: sa.Connection, ctl: Mapping[str, Any], now: datetime, contract: str
    ) -> AdmissionOutcome:
        age = None if ctl["heartbeat_at"] is None else _seconds(now - ctl["heartbeat_at"])
        capable, advertised = advertised_capability(ctl["effective_limits"], contract)
        queued = conn.scalar(
            sa.text(
                "SELECT count(*) FROM compute_attempts WHERE lane_id = :l AND state = 'QUEUED'"
            ),
            {"l": self.lane_id},
        )
        return admission_outcome(
            supervisor_state=SupervisorState(ctl["state"]),
            heartbeat=heartbeat_status(age, self.profile),
            capable=capable,
            recovery_required=ctl["recovery_required"],
            contract_advertised=advertised,
            queued_count=queued,
            profile=self.profile,
        )

    def _find_command(
        self, conn: sa.Connection, scope: TrustedScope, action: CommandAction, key: str
    ) -> Mapping[str, Any] | None:
        return (
            conn.execute(
                sa.text(
                    "SELECT request_sha256, response FROM compute_commands"
                    " WHERE organization_id = :o AND action = :act AND idempotency_key = :k"
                ),
                {"o": scope.organization_id, "act": action.value, "k": key},
            )
            .mappings()
            .one_or_none()
        )

    def _record_command(
        self,
        conn: sa.Connection,
        scope: TrustedScope,
        action: CommandAction,
        key: str,
        request_sha: str,
        job_id: uuid.UUID,
        attempt_id: uuid.UUID,
        response: Mapping[str, Any],
        now: datetime,
    ) -> uuid.UUID:
        command_id = uuid.uuid4()
        conn.execute(
            sa.text(
                "INSERT INTO compute_commands (command_id, organization_id, action,"
                " idempotency_key, request_sha256, job_id, attempt_id, response, created_at)"
                " VALUES (:c, :o, :act, :k, :h, :j, :a, CAST(:r AS jsonb), :now)"
            ),
            {
                "c": command_id,
                "o": scope.organization_id,
                "act": action.value,
                "k": key,
                "h": request_sha,
                "j": job_id,
                "a": attempt_id,
                "r": _json(dict(response)),
                "now": now,
            },
        )
        return command_id

    @staticmethod
    def _check_key(key: str) -> None:
        if not isinstance(key, str) or not IDEMPOTENCY_KEY.fullmatch(key):
            raise InputRejected("INVALID_IDEMPOTENCY_KEY", "idempotency key is malformed")

    def _insert_attempt(
        self,
        conn: sa.Connection,
        *,
        job_id: uuid.UUID,
        number: int,
        organization_id: uuid.UUID,
        now: datetime,
    ) -> uuid.UUID:
        attempt_id = uuid.uuid4()
        conn.execute(
            sa.text(
                "INSERT INTO compute_attempts (attempt_id, job_id, attempt_number, lane_id,"
                " organization_id, state, enqueued_at, queue_deadline_at)"
                " VALUES (:a, :j, :n, :l, :o, 'QUEUED', :now, :deadline)"
            ),
            {
                "a": attempt_id,
                "j": job_id,
                "n": number,
                "l": self.lane_id,
                "o": organization_id,
                "now": now,
                "deadline": now + timedelta(seconds=self.profile.queue_wait_s),
            },
        )
        return attempt_id

    # --- adapter-facing commands ---------------------------------------------------------

    def submit(
        self, scope: TrustedScope, contract: str, payload: Mapping[str, Any], idempotency_key: str,
        *, deduplicate: bool = False,
    ) -> Accepted:
        """Validate, then durably admit. Returns only after COMMIT (202 semantics)."""
        try:
            registration = self.registry.get(contract)
        except UnregisteredContract:
            raise InputRejected("UNKNOWN_CONTRACT", "handler contract is not registered") from None
        self._check_key(idempotency_key)
        validated = registration.handler.validate_input(payload)
        package = {
            "contract": registration.contract,
            "input_schema_version": registration.input_schema_version,
            "input": validated,
        }
        encoded = _json(package)
        if len(encoded.encode("utf-8")) > registration.max_input_bytes:
            raise InputRejected("INPUT_TOO_LARGE", "input package exceeds its registered bound")
        # Reuse/refresh is a command choice, not part of computational identity.
        # Keep existing non-deduplicating command hashes backwards-compatible.
        request_sha = sha256_hex({"action": "SUBMIT", "package": package,
                                  **({"deduplicate": True} if deduplicate else {})})
        rejection: AdmissionOutcome | None = None
        with self._tx() as conn:
            # Hash and store exactly what JSONB keeps (it rewrites e.g. -0.0 and 1e16), so the
            # claim/publish re-hash of the stored package matches; reject what it cannot keep.
            stored = self._jsonb_normalized(conn, encoded)
            if registration.handler.validate_input(stored["input"]) != stored["input"]:
                raise InputRejected("INPUT_NOT_REPRESENTABLE", "input changes when stored")
            encoded = _json(stored)
            input_sha = sha256_hex(stored)
            ctl, now = self._lock_control(conn)
            existing = self._find_command(conn, scope, CommandAction.SUBMIT, idempotency_key)
            if existing is not None:
                if existing["request_sha256"] != request_sha:
                    raise IdempotencyConflict("idempotency key reused with a different request")
                r = existing["response"]
                return Accepted(
                    uuid.UUID(r["job_id"]),
                    uuid.UUID(r["attempt_id"]),
                    AttemptState(r["state"]),
                    True,
                )
            self._expire_overdue(conn, now)
            if deduplicate:
                # The lane lock serializes lookup+admission with publication. Failed,
                # stopping and incomplete results never qualify. Reuse is available
                # during compute outage; GET still performs no queue mutations.
                duplicate = conn.execute(sa.text(
                    "SELECT j.job_id, a.attempt_id, a.state FROM compute_jobs j "
                    "JOIN compute_attempts a ON a.attempt_id = j.current_attempt_id "
                    "WHERE j.organization_id = :o AND j.lane_id = :l "
                    "AND j.handler_contract = :c AND j.input_sha256 = :sha "
                    "AND (a.state IN ('QUEUED', 'RUNNING') OR (a.state = 'SUCCEEDED' "
                    "AND a.result_manifest->>'planning_ready' = 'true')) "
                    "ORDER BY j.created_at DESC LIMIT 1"
                ), {"o": scope.organization_id, "l": self.lane_id,
                    "c": contract, "sha": input_sha}).mappings().one_or_none()
                if duplicate is not None:
                    response = {"job_id": str(duplicate["job_id"]),
                                "attempt_id": str(duplicate["attempt_id"]),
                                "state": duplicate["state"]}
                    self._record_command(conn, scope, CommandAction.SUBMIT, idempotency_key,
                                         request_sha, duplicate["job_id"], duplicate["attempt_id"],
                                         response, now)
                    self._audit(conn, "COMMAND_REUSED", job_id=duplicate["job_id"],
                                attempt_id=duplicate["attempt_id"],
                                details={"action": "SUBMIT", "input_sha256": input_sha})
                    return Accepted(duplicate["job_id"], duplicate["attempt_id"],
                                    AttemptState(duplicate["state"]), True)
            outcome = self._admission(conn, ctl, now, registration.contract)
            if outcome is not AdmissionOutcome.ACCEPT:
                rejection = outcome
            else:
                job_id = uuid.uuid4()
                attempt_id = self._insert_attempt(
                    conn, job_id=job_id, number=1, organization_id=scope.organization_id, now=now
                )
                conn.execute(
                    sa.text(
                        "INSERT INTO compute_jobs (job_id, lane_id, organization_id,"
                        " requested_by_ref, operation_kind, handler_contract,"
                        " input_schema_version, input_package, input_sha256, current_attempt_id,"
                        " state, created_at, updated_at) VALUES (:j, :l, :o, :actor, :kind, :c,"
                        " :v, CAST(:pkg AS jsonb), :sha, :a, 'QUEUED', :now, :now)"
                    ),
                    {
                        "j": job_id,
                        "l": self.lane_id,
                        "o": scope.organization_id,
                        "actor": scope.actor_ref,
                        "kind": registration.operation_kind.value,
                        "c": registration.contract,
                        "v": registration.input_schema_version,
                        "pkg": encoded,
                        "sha": input_sha,
                        "a": attempt_id,
                        "now": now,
                    },
                )
                response = {"job_id": str(job_id), "attempt_id": str(attempt_id), "state": "QUEUED"}
                command_id = self._record_command(
                    conn,
                    scope,
                    CommandAction.SUBMIT,
                    idempotency_key,
                    request_sha,
                    job_id,
                    attempt_id,
                    response,
                    now,
                )
                self._audit(
                    conn,
                    "COMMAND_ACCEPTED",
                    job_id=job_id,
                    attempt_id=attempt_id,
                    to_state="QUEUED",
                    details={
                        "action": "SUBMIT",
                        "command_id": str(command_id),
                        "input_sha256": input_sha,
                        "contract": registration.contract,
                    },
                )
        if rejection is not None:
            raise AdmissionRejected("new computation rejected", code=rejection.value)
        return Accepted(job_id, attempt_id, AttemptState.QUEUED, False)

    def _locked_scoped_job(
        self, conn: sa.Connection, scope: TrustedScope, job_id: uuid.UUID
    ) -> tuple[Mapping[str, Any], Mapping[str, Any]]:
        job = (
            conn.execute(
                sa.text(
                    "SELECT * FROM compute_jobs WHERE job_id = :j AND organization_id = :o"
                    " AND lane_id = :l FOR UPDATE"
                ),
                {"j": job_id, "o": scope.organization_id, "l": self.lane_id},
            )
            .mappings()
            .one_or_none()
        )
        if job is None:
            raise JobNotFound("job not found")
        attempt = (
            conn.execute(
                sa.text("SELECT * FROM compute_attempts WHERE attempt_id = :a FOR UPDATE"),
                {"a": job["current_attempt_id"]},
            )
            .mappings()
            .one()
        )
        return job, attempt

    def retry(self, scope: TrustedScope, job_id: uuid.UUID, idempotency_key: str) -> Accepted:
        """Manual retry: attempt n+1 against the exact saved input, at the queue tail."""
        self._check_key(idempotency_key)
        request_sha = sha256_hex({"action": "RETRY", "job_id": str(job_id)})
        rejection: AdmissionOutcome | None = None
        with self._tx() as conn:
            ctl, now = self._lock_control(conn)
            existing = self._find_command(conn, scope, CommandAction.RETRY, idempotency_key)
            if existing is not None:
                if existing["request_sha256"] != request_sha:
                    raise IdempotencyConflict("idempotency key reused with a different request")
                r = existing["response"]
                return Accepted(
                    uuid.UUID(r["job_id"]),
                    uuid.UUID(r["attempt_id"]),
                    AttemptState(r["state"]),
                    True,
                )
            self._expire_overdue(conn, now)
            job, attempt = self._locked_scoped_job(conn, scope, job_id)
            if not can_retry(AttemptState(attempt["state"])):
                raise JobStateConflict(f"cannot retry a {attempt['state']} job")
            outcome = self._admission(conn, ctl, now, job["handler_contract"])
            if outcome is not AdmissionOutcome.ACCEPT:
                rejection = outcome
            else:
                new_id = self._insert_attempt(
                    conn,
                    job_id=job_id,
                    number=attempt["attempt_number"] + 1,
                    organization_id=scope.organization_id,
                    now=now,
                )
                conn.execute(
                    sa.text(
                        "UPDATE compute_jobs SET current_attempt_id = :a, state = 'QUEUED',"
                        " updated_at = :now WHERE job_id = :j"
                    ),
                    {"a": new_id, "now": now, "j": job_id},
                )
                response = {"job_id": str(job_id), "attempt_id": str(new_id), "state": "QUEUED"}
                self._record_command(
                    conn,
                    scope,
                    CommandAction.RETRY,
                    idempotency_key,
                    request_sha,
                    job_id,
                    new_id,
                    response,
                    now,
                )
                self._audit(
                    conn,
                    "ATTEMPT_RETRIED",
                    job_id=job_id,
                    attempt_id=new_id,
                    to_state="QUEUED",
                    details={
                        "previous_attempt_id": str(attempt["attempt_id"]),
                        "previous_state": attempt["state"],
                        "input_sha256": job["input_sha256"],
                    },
                )
        if rejection is not None:
            raise AdmissionRejected("new computation rejected", code=rejection.value)
        return Accepted(job_id, new_id, AttemptState.QUEUED, False)

    def cancel(self, scope: TrustedScope, job_id: uuid.UUID, idempotency_key: str) -> CancelResult:
        """Queued work is cancelled at once; running work is asked to stop (completed=False)."""
        self._check_key(idempotency_key)
        request_sha = sha256_hex({"action": "CANCEL", "job_id": str(job_id)})
        with self._tx() as conn:
            _, now = self._lock_control(conn)
            existing = self._find_command(conn, scope, CommandAction.CANCEL, idempotency_key)
            if existing is not None:
                if existing["request_sha256"] != request_sha:
                    raise IdempotencyConflict("idempotency key reused with a different request")
                r = existing["response"]
                return CancelResult(
                    uuid.UUID(r["job_id"]),
                    uuid.UUID(r["attempt_id"]),
                    AttemptState(r["state"]),
                    r["completed"],
                    True,
                )
            self._expire_overdue(conn, now)
            _, attempt = self._locked_scoped_job(conn, scope, job_id)
            state = AttemptState(attempt["state"])
            if state is AttemptState.QUEUED:
                self._transition(
                    conn, attempt, AttemptState.CANCELLED, now, reason=ReasonCode.CANCEL_REQUESTED
                )
                result_state, completed = AttemptState.CANCELLED, True
            elif state is AttemptState.RUNNING:
                self._transition(
                    conn,
                    attempt,
                    AttemptState.STOPPING,
                    now,
                    extra={"stop_requested_at": now, "stop_reason": ReasonCode.CANCEL_REQUESTED},
                )
                result_state, completed = AttemptState.STOPPING, False
            elif state is AttemptState.STOPPING and attempt["stop_reason"] == "CANCEL_REQUESTED":
                result_state, completed = AttemptState.STOPPING, False
            else:
                raise JobStateConflict(f"cannot cancel a {state} job")
            response = {
                "job_id": str(job_id),
                "attempt_id": str(attempt["attempt_id"]),
                "state": result_state.value,
                "completed": completed,
            }
            self._record_command(
                conn,
                scope,
                CommandAction.CANCEL,
                idempotency_key,
                request_sha,
                job_id,
                attempt["attempt_id"],
                response,
                now,
            )
            self._audit(
                conn,
                "ATTEMPT_CANCELLED" if completed else "CANCEL_REQUESTED",
                job_id=job_id,
                attempt_id=attempt["attempt_id"],
                from_state=state.value,
                to_state=result_state.value,
                reason_code=ReasonCode.CANCEL_REQUESTED,
            )
        return CancelResult(job_id, attempt["attempt_id"], result_state, completed, False)

    # --- reads (no locks, no mutation) -----------------------------------------------------

    def get_job(self, scope: TrustedScope, job_id: uuid.UUID) -> JobView:
        with self._read() as conn:
            job = (
                conn.execute(
                    sa.text(
                        "SELECT * FROM compute_jobs WHERE job_id = :j AND organization_id = :o"
                    ),
                    {"j": job_id, "o": scope.organization_id},
                )
                .mappings()
                .one_or_none()
            )
            if job is None:
                raise JobNotFound("job not found")
            attempts = (
                conn.execute(
                    sa.text(
                        f"SELECT {_ATTEMPT_VIEW_COLUMNS} FROM compute_attempts"
                        " WHERE job_id = :j ORDER BY attempt_number"
                    ),
                    {"j": job_id},
                )
                .mappings()
                .all()
            )
        return JobView(
            job_id=job["job_id"],
            organization_id=job["organization_id"],
            operation_kind=OperationKind(job["operation_kind"]),
            handler_contract=job["handler_contract"],
            input_sha256=job["input_sha256"],
            state=AttemptState(job["state"]),
            current_attempt_id=job["current_attempt_id"],
            created_at=job["created_at"],
            updated_at=job["updated_at"],
            attempts=tuple(_attempt_view(a) for a in attempts),
        )

    def read_attempt(self, attempt_id: uuid.UUID) -> AttemptView:
        with self._read() as conn:
            row = (
                conn.execute(
                    sa.text(
                        f"SELECT {_ATTEMPT_VIEW_COLUMNS} FROM compute_attempts"
                        " WHERE attempt_id = :a"
                    ),
                    {"a": attempt_id},
                )
                .mappings()
                .one()
            )
        return _attempt_view(row)

    def control(self) -> ControlView:
        with self._read() as conn:
            row = (
                conn.execute(
                    sa.text("SELECT * FROM compute_control WHERE lane_id = :l"), {"l": self.lane_id}
                )
                .mappings()
                .one()
            )
        return ControlView(
            lane_id=row["lane_id"],
            state=SupervisorState(row["state"]),
            supervisor_id=row["supervisor_id"],
            generation=row["generation"],
            host_identity=row["host_identity"],
            heartbeat_at=row["heartbeat_at"],
            active_attempt_id=row["active_attempt_id"],
            recovery_required=row["recovery_required"],
            effective_limits=row["effective_limits"],
        )

    def audit_events(self, job_id: uuid.UUID) -> list[dict[str, Any]]:
        with self._read() as conn:
            rows = conn.execute(
                sa.text(
                    "SELECT event_type, from_state, to_state, reason_code, details,"
                    " supervisor_generation FROM compute_audit_events"
                    " WHERE job_id = :j ORDER BY event_id"
                ),
                {"j": job_id},
            ).mappings()
            return [dict(r) for r in rows]

    # --- supervisor ownership --------------------------------------------------------------

    def acquire_ownership(
        self, *, supervisor_id: uuid.UUID, host_identity: str, effective_limits: dict[str, Any]
    ) -> Ownership | None:
        """Take the lane unless another owner is healthy. Never takes over a fresh owner."""
        with self._tx() as conn:
            ctl, now = self._lock_control(conn)
            if ctl["state"] != SupervisorState.OFFLINE and ctl["supervisor_id"] not in (
                None,
                supervisor_id,
            ):
                age = None if ctl["heartbeat_at"] is None else _seconds(now - ctl["heartbeat_at"])
                status = heartbeat_status(age, self.profile)
                if status in (HeartbeatStatus.FRESH, HeartbeatStatus.FUTURE):
                    return None
            occupied = conn.scalar(
                sa.text(
                    "SELECT count(*) FROM compute_attempts WHERE lane_id = :l"
                    " AND state IN ('RUNNING', 'STOPPING')"
                ),
                {"l": self.lane_id},
            )
            recovery = bool(occupied) or ctl["active_attempt_id"] is not None
            generation = ctl["generation"] + 1
            state = SupervisorState.RECOVERING if recovery else SupervisorState.STARTING
            conn.execute(
                sa.text(
                    "UPDATE compute_control SET supervisor_id = :s, generation = :g,"
                    " host_identity = :h, state = :state, heartbeat_at = :now,"
                    " recovery_required = :rec, effective_limits = CAST(:lim AS jsonb),"
                    " updated_at = :now WHERE lane_id = :l"
                ),
                {
                    "s": supervisor_id,
                    "g": generation,
                    "h": host_identity[:512],
                    "state": state.value,
                    "now": now,
                    "rec": recovery,
                    "lim": _json(effective_limits),
                    "l": self.lane_id,
                },
            )
            own = Ownership(self.lane_id, supervisor_id, generation)
            self._audit(
                conn,
                "OWNERSHIP_ACQUIRED",
                own=own,
                from_state=ctl["state"],
                to_state=state.value,
                details={
                    "previous_supervisor_id": str(ctl["supervisor_id"])
                    if ctl["supervisor_id"]
                    else None,
                    "previous_generation": ctl["generation"],
                    "host_identity": host_identity[:512],
                },
            )
        return own

    def heartbeat(self, own: Ownership) -> bool:
        """Short conditional write. False means this owner/generation was fenced."""
        with self._tx(lock_timeout_ms=1_000) as conn:
            updated = conn.execute(
                sa.text(
                    "UPDATE compute_control SET heartbeat_at = clock_timestamp(),"
                    " updated_at = clock_timestamp() WHERE lane_id = :l AND supervisor_id = :s"
                    " AND generation = :g AND state <> 'OFFLINE'"
                ),
                {"l": self.lane_id, "s": own.supervisor_id, "g": own.generation},
            )
            return updated.rowcount == 1

    def set_state(self, own: Ownership, state: SupervisorState) -> bool:
        state = SupervisorState(state)
        with self._tx() as conn:
            ctl, now = self._lock_control(conn)
            if not self._is_owner(ctl, own) or ctl["state"] == SupervisorState.OFFLINE:
                return False
            if state is SupervisorState.READY and (
                ctl["recovery_required"] or ctl["state"] == SupervisorState.DRAINING
            ):
                return False
            conn.execute(
                sa.text(
                    "UPDATE compute_control SET state = :state, updated_at = :now,"
                    " heartbeat_at = CASE WHEN :state = 'OFFLINE' THEN NULL ELSE heartbeat_at END"
                    " WHERE lane_id = :l"
                ),
                {"state": state.value, "now": now, "l": self.lane_id},
            )
            self._audit(
                conn, "SUPERVISOR_STATE", own=own, from_state=ctl["state"], to_state=state.value
            )
        return True

    def release(self, own: Ownership) -> bool:
        return self.set_state(own, SupervisorState.OFFLINE)

    # --- claim and execution bookkeeping -----------------------------------------------------

    def _fail_unstarted(
        self, conn: sa.Connection, row: Mapping[str, Any], reason: ReasonCode, now: datetime
    ) -> None:
        self._transition(
            conn,
            row,
            AttemptState.FAILED,
            now,
            reason=reason,
            extra={"error": {"code": reason.value, "boundary_created": False}},
        )
        self._audit(
            conn,
            "ATTEMPT_FAILED_BEFORE_START",
            job_id=row["job_id"],
            attempt_id=row["attempt_id"],
            from_state="QUEUED",
            to_state="FAILED",
            reason_code=reason,
        )

    def claim_next(self, own: Ownership) -> ClaimedAttempt | None:
        """Claim the oldest current QUEUED attempt. Commit happens before any child starts."""
        with self._tx() as conn:
            ctl, now = self._lock_control(conn)
            self._require_owner(ctl, own)
            if (
                ctl["state"] != SupervisorState.READY
                or ctl["active_attempt_id"] is not None
                or ctl["recovery_required"]
            ):
                return None
            self._expire_overdue(conn, now)
            while True:
                row = (
                    conn.execute(
                        sa.text(
                            "SELECT a.attempt_id, a.job_id, a.attempt_number, a.state,"
                            " a.enqueued_at, j.organization_id, j.operation_kind,"
                            " j.handler_contract, j.input_schema_version, j.input_package,"
                            " j.input_sha256 FROM compute_attempts a JOIN compute_jobs j"
                            " ON j.job_id = a.job_id AND j.current_attempt_id = a.attempt_id"
                            " WHERE a.lane_id = :l AND a.state = 'QUEUED'"
                            " ORDER BY a.enqueued_at, a.attempt_id LIMIT 1 FOR UPDATE OF a, j"
                        ),
                        {"l": self.lane_id},
                    )
                    .mappings()
                    .one_or_none()
                )
                if row is None:
                    return None
                package = row["input_package"]
                try:
                    registration = self.registry.get(row["handler_contract"])
                except UnregisteredContract:
                    self._fail_unstarted(conn, row, ReasonCode.UNREGISTERED_CONTRACT, now)
                    continue
                try:
                    intact = (
                        sha256_hex(package) == row["input_sha256"]
                        and registration.operation_kind.value == row["operation_kind"]
                        and registration.input_schema_version == row["input_schema_version"]
                        and package.get("contract") == registration.contract
                        and registration.handler.validate_input(package["input"])
                        == package["input"]
                    )
                except (InputRejected, KeyError, TypeError, ValueError, AttributeError):
                    intact = False
                if not intact:
                    self._fail_unstarted(conn, row, ReasonCode.INPUT_INTEGRITY, now)
                    continue
                kind = OperationKind(row["operation_kind"])
                budget = operation_budget_s(kind, self.profile)
                steps = registration.handler.steps(package["input"], self.profile)
                cutoffs = [s.cutoff_s for s in steps if s.cutoff_s is not None]
                deadline = now + timedelta(seconds=budget)
                primary = now + timedelta(seconds=min(cutoffs)) if cutoffs else None
                token = uuid.uuid4()
                self._transition(
                    conn,
                    row,
                    AttemptState.RUNNING,
                    now,
                    extra={
                        "supervisor_id": own.supervisor_id,
                        "supervisor_generation": own.generation,
                        "execution_token": token,
                        "started_at": now,
                        "execution_deadline_at": deadline,
                        "primary_deadline_at": primary,
                    },
                )
                conn.execute(
                    sa.text(
                        "UPDATE compute_control SET active_attempt_id = :a, updated_at = :now"
                        " WHERE lane_id = :l"
                    ),
                    {"a": row["attempt_id"], "now": now, "l": self.lane_id},
                )
                self._audit(
                    conn,
                    "ATTEMPT_CLAIMED",
                    job_id=row["job_id"],
                    attempt_id=row["attempt_id"],
                    from_state="QUEUED",
                    to_state="RUNNING",
                    own=own,
                    details={
                        "budget_s": budget,
                        "primary_cutoff_s": min(cutoffs) if cutoffs else None,
                        "queue_wait_s": round(_seconds(now - row["enqueued_at"]), 3),
                    },
                )
                return ClaimedAttempt(
                    job_id=row["job_id"],
                    attempt_id=row["attempt_id"],
                    attempt_number=row["attempt_number"],
                    organization_id=row["organization_id"],
                    contract=registration.contract,
                    operation_kind=kind,
                    input_package=package,
                    input_sha256=row["input_sha256"],
                    execution_token=token,
                    supervisor_generation=own.generation,
                    started_at=now,
                    execution_deadline_at=deadline,
                    primary_deadline_at=primary,
                    budget_s=budget,
                )

    def _lock_claimed(
        self, conn: sa.Connection, own: Ownership, claim: ClaimedAttempt
    ) -> tuple[Mapping[str, Any], datetime, Mapping[str, Any], Mapping[str, Any]]:
        ctl, now = self._lock_control(conn)
        self._require_owner(ctl, own)
        job = (
            conn.execute(
                sa.text("SELECT * FROM compute_jobs WHERE job_id = :j FOR UPDATE"),
                {"j": claim.job_id},
            )
            .mappings()
            .one()
        )
        attempt = (
            conn.execute(
                sa.text("SELECT * FROM compute_attempts WHERE attempt_id = :a FOR UPDATE"),
                {"a": claim.attempt_id},
            )
            .mappings()
            .one()
        )
        if (
            attempt["execution_token"] != claim.execution_token
            or attempt["supervisor_generation"] != own.generation
        ):
            raise Fenced("attempt token or generation mismatch", code="PUBLICATION_FENCED")
        return ctl, now, job, attempt

    def prepare_boundary(self, own: Ownership, claim: ClaimedAttempt, phase: str) -> bool:
        """Invalidate the previous step's identity BEFORE a new child can be spawned.

        A crash between spawning and recording the new boundary must quarantine recovery,
        never prove cleanup using the already-empty boundary from the previous step.
        """
        with self._tx() as conn:
            _, now, _, attempt = self._lock_claimed(conn, own, claim)
            if attempt["state"] != AttemptState.RUNNING or now >= attempt["execution_deadline_at"]:
                return False
            conn.execute(
                sa.text(
                    "UPDATE compute_attempts SET execution_boundary = NULL, current_phase = :p"
                    " WHERE attempt_id = :a"
                ),
                {"p": phase[:64], "a": claim.attempt_id},
            )
        return True

    def record_boundary(
        self, own: Ownership, claim: ClaimedAttempt, boundary: Mapping[str, Any], phase: str
    ) -> bool:
        with self._tx() as conn:
            _, now, _, attempt = self._lock_claimed(conn, own, claim)
            if attempt["state"] not in _OCCUPYING:
                return False
            conn.execute(
                sa.text(
                    "UPDATE compute_attempts SET execution_boundary = CAST(:b AS jsonb),"
                    " current_phase = :p WHERE attempt_id = :a"
                ),
                {"b": _json(dict(boundary)), "p": phase[:64], "a": claim.attempt_id},
            )
            self._audit(
                conn,
                "BOUNDARY_STARTED",
                job_id=claim.job_id,
                attempt_id=claim.attempt_id,
                own=own,
                details={
                    "phase": phase[:64],
                    "boundary": {k: v for k, v in boundary.items() if k != "nonce"},
                },
            )
        return True

    def request_stop(
        self, own: Ownership, claim: ClaimedAttempt, reason: ReasonCode
    ) -> AttemptState:
        """RUNNING -> STOPPING (revokes publication). An existing stop reason is kept."""
        with self._tx() as conn:
            _, now, _, attempt = self._lock_claimed(conn, own, claim)
            state = AttemptState(attempt["state"])
            if state is not AttemptState.RUNNING:
                return state
            self._transition(
                conn,
                attempt,
                AttemptState.STOPPING,
                now,
                extra={"stop_requested_at": now, "stop_reason": ReasonCode(reason).value},
            )
            self._audit(
                conn,
                "STOP_REQUESTED",
                job_id=claim.job_id,
                attempt_id=claim.attempt_id,
                own=own,
                from_state="RUNNING",
                to_state="STOPPING",
                reason_code=ReasonCode(reason),
            )
        return AttemptState.STOPPING

    def finalize(
        self,
        own: Ownership,
        claim: ClaimedAttempt,
        *,
        failure_reason: ReasonCode | None = None,
        error: Mapping[str, Any] | None = None,
        diagnostics: Mapping[str, Any] | None = None,
    ) -> AttemptState:
        """Record a cleaned-up non-success outcome and release the slot.

        The caller asserts that the execution boundary has exited and cleanup is confirmed.
        A STOPPING attempt ends in the state its recorded stop reason implies; a RUNNING
        attempt whose child already exited ends FAILED with ``failure_reason``.
        """
        with self._tx() as conn:
            _, now, _, attempt = self._lock_claimed(conn, own, claim)
            state = AttemptState(attempt["state"])
            if state is AttemptState.RUNNING:
                if failure_reason is None:
                    raise ValueError("a running attempt needs a failure reason")
                target, reason = AttemptState.FAILED, ReasonCode(failure_reason).value
            elif state is AttemptState.STOPPING:
                reason = attempt["stop_reason"]
                target = final_state_for_stop_reason(ReasonCode(reason))
            else:
                raise JobStateConflict(f"attempt is already {state}")
            self._transition(
                conn,
                attempt,
                target,
                now,
                reason=reason,
                extra={
                    "cleanup_confirmed_at": now,
                    "error": dict(error) if error else {"code": reason},
                    "diagnostics_merge": dict(diagnostics or {}),
                },
            )
            self._release_slot(conn, claim.attempt_id, now)
            self._audit(
                conn,
                "ATTEMPT_FINALIZED",
                job_id=claim.job_id,
                attempt_id=claim.attempt_id,
                own=own,
                from_state=state.value,
                to_state=target.value,
                reason_code=reason,
            )
        return target

    # --- fenced publication ------------------------------------------------------------------

    def publish(
        self, own: Ownership, claim: ClaimedAttempt, package: Mapping[str, Any]
    ) -> dict[str, Any]:
        """Atomically persist the domain result, success state, audit and slot release.

        Raises Fenced when authority was revoked, PublicationRejected when the domain
        publisher refuses (everything rolled back) and CommitUncertain when COMMIT did not
        acknowledge.
        """
        registration = self.registry.get(claim.contract)
        if len(_json(dict(package)).encode("utf-8")) > registration.max_output_bytes:
            raise PublicationRejected(ReasonCode.OUTPUT_TOO_LARGE.value)
        try:
            conn = self.engine.connect()
        except (OperationalError, InterfaceError) as exc:
            raise QueueStorageUnavailable("queue storage unavailable") from exc
        try:
            transaction = conn.begin()
            try:
                self._set_timeouts(conn, self._lock_timeout_ms, self._statement_timeout_ms)
                _, now, job, attempt = self._lock_claimed(conn, own, claim)
                deadline = attempt["execution_deadline_at"]
                if job["current_attempt_id"] != claim.attempt_id:
                    raise Fenced("attempt is no longer current")
                if attempt["state"] != AttemptState.RUNNING or attempt["stop_requested_at"]:
                    raise Fenced(f"attempt is {attempt['state']}; publication revoked")
                if now >= deadline:
                    raise Fenced("execution deadline reached before publication")
                remaining_ms = int(_seconds(deadline - now) * 1000)
                self._set_timeouts(conn, remaining_ms, remaining_ms)
                if not (
                    sha256_hex(job["input_package"]) == job["input_sha256"] == claim.input_sha256
                ):
                    raise Fenced("input identity changed")
                identity = PublicationIdentity(
                    job_id=claim.job_id,
                    attempt_id=claim.attempt_id,
                    organization_id=job["organization_id"],
                    handler_contract=claim.contract,
                    input_sha256=claim.input_sha256,
                )
                manifest = registration.publisher.publish(conn, identity, package)
                if not isinstance(manifest, dict):
                    raise PublicationRejected(ReasonCode.OUTPUT_INVALID.value)
                encoded = _json(manifest)
                final_now = conn.scalar(sa.text("SELECT clock_timestamp()"))
                if final_now >= deadline:
                    raise Fenced("execution deadline reached during publication")
                self._transition(
                    conn,
                    attempt,
                    AttemptState.SUCCEEDED,
                    final_now,
                    extra={"result_manifest": manifest, "cleanup_confirmed_at": final_now},
                )
                self._release_slot(conn, claim.attempt_id, final_now)
                self._audit(
                    conn,
                    "ATTEMPT_PUBLISHED",
                    job_id=claim.job_id,
                    attempt_id=claim.attempt_id,
                    own=own,
                    from_state="RUNNING",
                    to_state="SUCCEEDED",
                    details={"manifest_bytes": len(encoded)},
                )
            except BaseException:
                try:
                    transaction.rollback()
                except DBAPIError:
                    pass
                raise
            try:
                self._commit(transaction)
            except DBAPIError as exc:
                raise CommitUncertain("publication commit was not acknowledged") from exc
            return manifest
        except (OperationalError, InterfaceError) as exc:
            raise QueueStorageUnavailable("queue storage unavailable") from exc
        finally:
            conn.close()

    def reconcile_publication(self, own: Ownership, claim: ClaimedAttempt) -> str:
        """Resolve an uncertain COMMIT by identity: COMMITTED, ABSENT or OTHER_<state>."""
        with self._tx() as conn:
            ctl, _ = self._lock_control(conn)
            self._require_owner(ctl, own)
            attempt = (
                conn.execute(
                    sa.text("SELECT * FROM compute_attempts WHERE attempt_id = :a FOR UPDATE"),
                    {"a": claim.attempt_id},
                )
                .mappings()
                .one()
            )
            mine = attempt["execution_token"] == claim.execution_token
            if mine and attempt["state"] == AttemptState.SUCCEEDED:
                outcome = "COMMITTED"
            elif mine and attempt["state"] == AttemptState.RUNNING:
                outcome = "ABSENT"
            else:
                outcome = f"OTHER_{attempt['state']}"
            self._audit(
                conn,
                "PUBLICATION_RECONCILED",
                job_id=claim.job_id,
                attempt_id=claim.attempt_id,
                own=own,
                details={"outcome": outcome, "uncertain_commit": True},
            )
        return outcome

    # --- recovery --------------------------------------------------------------------------

    def begin_recovery(self, own: Ownership) -> list[RecoveryItem]:
        """Fence every occupying attempt of a previous owner: RUNNING -> STOPPING(WORKER_LOST)."""
        with self._tx() as conn:
            ctl, now = self._lock_control(conn)
            self._require_owner(ctl, own)
            rows = (
                conn.execute(
                    sa.text(
                        "SELECT * FROM compute_attempts WHERE lane_id = :l"
                        " AND state IN ('RUNNING', 'STOPPING') ORDER BY started_at FOR UPDATE"
                    ),
                    {"l": self.lane_id},
                )
                .mappings()
                .all()
            )
            items = []
            for row in rows:
                stop_reason = row["stop_reason"]
                if row["state"] == AttemptState.RUNNING:
                    stop_reason = ReasonCode.WORKER_LOST.value
                    self._transition(
                        conn,
                        row,
                        AttemptState.STOPPING,
                        now,
                        extra={"stop_requested_at": now, "stop_reason": stop_reason},
                    )
                    self._audit(
                        conn,
                        "RECOVERY_STOP_RECORDED",
                        job_id=row["job_id"],
                        attempt_id=row["attempt_id"],
                        own=own,
                        from_state="RUNNING",
                        to_state="STOPPING",
                        reason_code=stop_reason,
                        details={"lost_generation": row["supervisor_generation"]},
                    )
                items.append(
                    RecoveryItem(
                        attempt_id=row["attempt_id"],
                        job_id=row["job_id"],
                        state=AttemptState.STOPPING,
                        stop_reason=stop_reason,
                        execution_boundary=row["execution_boundary"],
                        supervisor_id=row["supervisor_id"],
                        supervisor_generation=row["supervisor_generation"],
                    )
                )
            if items:
                conn.execute(
                    sa.text(
                        "UPDATE compute_control SET recovery_required = true,"
                        " state = CASE WHEN state = 'QUARANTINED' THEN state ELSE 'RECOVERING' END,"
                        " updated_at = :now WHERE lane_id = :l"
                    ),
                    {"now": now, "l": self.lane_id},
                )
        return items

    def _finalize_stopping(
        self,
        conn: sa.Connection,
        attempt_id: uuid.UUID,
        evidence: Mapping[str, Any],
        now: datetime,
        *,
        own: Ownership | None,
        event: str,
    ) -> AttemptState:
        attempt = (
            conn.execute(
                sa.text(
                    "SELECT * FROM compute_attempts WHERE attempt_id = :a AND lane_id = :l"
                    " FOR UPDATE"
                ),
                {"a": attempt_id, "l": self.lane_id},
            )
            .mappings()
            .one_or_none()
        )
        if attempt is None:
            raise JobNotFound("attempt not found")
        if attempt["state"] != AttemptState.STOPPING:
            raise JobStateConflict(f"attempt is {attempt['state']}, not STOPPING")
        reason = attempt["stop_reason"]
        target = final_state_for_stop_reason(ReasonCode(reason))
        self._transition(
            conn,
            attempt,
            target,
            now,
            reason=reason,
            extra={
                "cleanup_confirmed_at": now,
                "error": {"code": reason},
                "diagnostics_merge": {"recovery_evidence": dict(evidence)},
            },
        )
        self._release_slot(conn, attempt_id, now)
        self._audit(
            conn,
            event,
            job_id=attempt["job_id"],
            attempt_id=attempt_id,
            own=own,
            from_state="STOPPING",
            to_state=target.value,
            reason_code=reason,
            details={"evidence_method": evidence.get("method")},
        )
        return target

    def finalize_recovered(
        self, own: Ownership, attempt_id: uuid.UUID, evidence: Mapping[str, Any]
    ) -> AttemptState:
        """Finalize a lost attempt once its boundary is confirmed gone (``evidence``)."""
        with self._tx() as conn:
            ctl, now = self._lock_control(conn)
            self._require_owner(ctl, own)
            return self._finalize_stopping(
                conn, attempt_id, evidence, now, own=own, event="ATTEMPT_RECOVERED"
            )

    def quarantine(self, own: Ownership, reason: str) -> bool:
        with self._tx() as conn:
            ctl, now = self._lock_control(conn)
            if not self._is_owner(ctl, own):
                return False
            conn.execute(
                sa.text(
                    "UPDATE compute_control SET state = 'QUARANTINED', recovery_required = true,"
                    " updated_at = :now WHERE lane_id = :l"
                ),
                {"now": now, "l": self.lane_id},
            )
            self._audit(
                conn,
                "LANE_QUARANTINED",
                own=own,
                from_state=ctl["state"],
                to_state="QUARANTINED",
                details={"reason": reason[:200]},
            )
        return True

    def finish_recovery(self, own: Ownership) -> bool:
        """Clear recovery once no attempt occupies the lane; the owner may then go READY."""
        with self._tx() as conn:
            ctl, now = self._lock_control(conn)
            if not self._is_owner(ctl, own):
                return False
            occupied = conn.scalar(
                sa.text(
                    "SELECT count(*) FROM compute_attempts WHERE lane_id = :l"
                    " AND state IN ('RUNNING', 'STOPPING')"
                ),
                {"l": self.lane_id},
            )
            if occupied or ctl["active_attempt_id"] is not None:
                return False
            conn.execute(
                sa.text(
                    "UPDATE compute_control SET recovery_required = false,"
                    " state = CASE WHEN state IN ('RECOVERING', 'QUARANTINED') THEN 'STARTING'"
                    " ELSE state END, updated_at = :now WHERE lane_id = :l"
                ),
                {"now": now, "l": self.lane_id},
            )
        return True

    def operator_attest_cleanup(
        self, attempt_id: uuid.UUID, operator_ref: str, note: str
    ) -> AttemptState:
        """Administrative recovery: an operator attests the old boundary is gone (ADR 0005 A1).

        Recorded as OPERATOR_ATTESTATION evidence, distinct from automatic proof.
        """
        if not operator_ref or len(operator_ref) > 200:
            raise ValueError("operator_ref must be 1-200 characters")
        evidence = {
            "method": "OPERATOR_ATTESTATION",
            "operator_ref": operator_ref,
            "note": note[:500],
        }
        with self._tx() as conn:
            _, now = self._lock_control(conn)
            target = self._finalize_stopping(
                conn, attempt_id, evidence, now, own=None, event="OPERATOR_ATTESTED_CLEANUP"
            )
            remaining = conn.scalar(
                sa.text(
                    "SELECT count(*) FROM compute_attempts WHERE lane_id = :l"
                    " AND state IN ('RUNNING', 'STOPPING')"
                ),
                {"l": self.lane_id},
            )
            if not remaining:
                conn.execute(
                    sa.text(
                        "UPDATE compute_control SET recovery_required = false, updated_at = :now"
                        " WHERE lane_id = :l"
                    ),
                    {"now": now, "l": self.lane_id},
                )
        return target

    def expire_overdue(self) -> int:
        with self._tx() as conn:
            _, now = self._lock_control(conn)
            return self._expire_overdue(conn, now)
