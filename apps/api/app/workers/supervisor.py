"""Compute supervisor: ownership, heartbeat, claims, deadlines, containment and publication.

One supervisor owns the lane and runs at most one attempt at a time, each step in a fresh
controlled child. The loop never blocks on a child, model or solver: it polls, and a
separate thread writes heartbeats with its own short transactions. Worker loss never
causes automatic recomputation, and a slot is released only after cleanup is confirmed.

Run: ``python -m app.workers.supervisor --registry production`` with DATABASE_URL set.
"""

import argparse
import json
import logging
import os
import signal
import sys
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.repositories.jobs import (
    ClaimedAttempt,
    CommitUncertain,
    Fenced,
    JobStateConflict,
    OwnershipLost,
    QueueRepository,
    QueueStorageUnavailable,
    create_queue_engine,
)
from app.services.jobs.contracts import (
    PRODUCTION_PROFILE,
    AttemptState,
    ReasonCode,
    RuntimeProfile,
    StepOutcome,
    StepSpec,
    StepStatus,
    StepWindow,
    SupervisorState,
    canonical_json,
)
from app.services.jobs.policies import (
    plan_step_window,
    should_run_step,
    supervisor_advertisement,
)
from app.services.jobs.registry import PublicationRejected, Registration, Registry
from app.workers.publication import reason_for, step_outcome
from app.workers.recovery import containment_evidence

logger = logging.getLogger("pantrypulse.worker")
API_ROOT = Path(__file__).resolve().parents[2]


def log_event(event: str, **fields: Any) -> None:
    """Structured JSON line with identifiers and counts only: no tokens or payloads."""
    logger.info(canonical_json({"event": event, **{k: _safe(v) for k, v in fields.items()}}))


def _safe(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(value)


@dataclass(frozen=True, slots=True)
class SupervisorConfig:
    registry_name: str
    profile: RuntimeProfile = PRODUCTION_PROFILE
    tick_s: float = 0.05
    state_poll_s: float = 0.25
    ownership_check_s: float | None = None
    recovery_recheck_s: float = 2.0
    stop_confirm_timeout_s: float = 5.0
    expiry_scan_s: float = 1.0
    python: str = sys.executable


@dataclass
class StepRun:
    spec: StepSpec
    window: StepWindow
    handle: Any
    soft_at: float
    force_at: float
    hard_at: float
    started_at: float
    timed_out: bool = False
    kill_sent_at: float | None = None
    term_sent: bool = False
    overflowed: bool = False
    exited_at: float | None = None
    cleanup_deadline: float | None = None


@dataclass
class Execution:
    claim: ClaimedAttempt
    registration: Registration
    validated: dict[str, Any]
    steps: tuple[StepSpec, ...]
    mono_start: float
    hard_deadline: float
    soft_deadline: float
    index: int = 0
    outcomes: list[StepOutcome] = field(default_factory=list)
    current: StepRun | None = None
    stopping: bool = False
    kill_at: float | None = None
    kill_sent_at: float | None = None
    cleanup_deadline: float | None = None
    cleanup_quarantined: bool = False
    publish_pending: bool = False
    uncertain: bool = False
    last_state_poll: float = 0.0


def _overflowing(handle: Any) -> bool:
    return bool(getattr(getattr(handle, "stdout", None), "overflow", False))


class Supervisor:
    def __init__(
        self,
        repo: QueueRepository,
        registry: Registry,
        driver: Any,
        config: SupervisorConfig,
        *,
        clock=time.monotonic,
        supervisor_id: uuid.UUID | None = None,
    ):
        self.repo = repo
        self.registry = registry
        self.driver = driver
        self.config = config
        self.profile = config.profile
        self.clock = clock
        self.supervisor_id = supervisor_id or uuid.uuid4()
        self.own = None
        self.active: Execution | None = None
        self.quarantined = False
        self.draining = False
        self.ownership_lost = False
        self.closed = False
        self._fenced = threading.Event()
        self._hb_stop = threading.Event()
        self._hb_thread: threading.Thread | None = None
        self._last_ownership_check = 0.0
        self._last_recovery_check = 0.0
        self._last_expiry_scan = 0.0

    # --- startup, heartbeat and recovery -------------------------------------------------

    def start(self) -> bool:
        if not self.driver.capable:
            log_event("COMPUTE_CAPABILITY_MISSING", capability="process_containment")
            return False
        advertisement = supervisor_advertisement(
            self.profile,
            handler_contracts=self.registry.contracts(),
            process_containment=True,
        )
        own = self.repo.acquire_ownership(
            supervisor_id=self.supervisor_id,
            host_identity=self.driver.host_identity_text(),
            effective_limits=advertisement,
        )
        if own is None:
            log_event("LANE_OWNED_ELSEWHERE", supervisor_id=self.supervisor_id)
            return False
        self.own = own
        log_event("OWNERSHIP_ACQUIRED", supervisor_id=own.supervisor_id, generation=own.generation)
        self._start_heartbeat()
        self._recovery_pass()
        return True

    def _start_heartbeat(self) -> None:
        self._hb_stop.clear()
        self._hb_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._hb_thread.start()

    def _heartbeat_loop(self) -> None:
        while not self._hb_stop.wait(self.profile.heartbeat_interval_s):
            try:
                if not self.repo.heartbeat(self.own):
                    self._fenced.set()
                    return
            except QueueStorageUnavailable:
                log_event("HEARTBEAT_STORAGE_UNAVAILABLE")
            except Exception as exc:  # noqa: BLE001 - keep beating; report the type only
                log_event("HEARTBEAT_ERROR", error_type=type(exc).__name__)

    def pause_heartbeat(self) -> None:
        self._hb_stop.set()
        if self._hb_thread is not None:
            self._hb_thread.join(5)

    def _recovery_pass(self) -> bool:
        """Resolve occupying attempts with evidence; quarantine what cannot be resolved."""
        items = self.repo.begin_recovery(self.own)
        unresolved = []
        for item in items:
            evidence = containment_evidence(
                self.driver, item, timeout_s=self.config.stop_confirm_timeout_s
            )
            if evidence is None:
                unresolved.append(item.attempt_id)
                continue
            state = self.repo.finalize_recovered(self.own, item.attempt_id, evidence)
            log_event(
                "ATTEMPT_RECOVERED",
                attempt_id=item.attempt_id,
                state=state.value,
                evidence=evidence.get("method"),
            )
        if unresolved:
            if not self.quarantined:
                self.repo.quarantine(self.own, "BOUNDARY_UNVERIFIABLE")
                log_event("LANE_QUARANTINED", unresolved=len(unresolved))
            self.quarantined = True
            return False
        if not self.repo.finish_recovery(self.own):
            return False
        if not self.draining:
            self.repo.set_state(self.own, SupervisorState.READY)
        self.quarantined = False
        log_event("SUPERVISOR_READY", generation=self.own.generation)
        return True

    # --- main loop -----------------------------------------------------------------------------

    def tick(self) -> None:
        if self.closed or self.ownership_lost or self.own is None:
            return
        now = self.clock()
        try:
            if self._fenced.is_set() or self._ownership_changed(now):
                self._on_ownership_lost()
                return
            if self.active is not None:
                self._drive(self.active, now)
            elif self.quarantined:
                if now - self._last_recovery_check >= self.config.recovery_recheck_s:
                    self._last_recovery_check = now
                    self._recovery_pass()
            elif not self.draining:
                mono_start = self.clock()
                claim = self.repo.claim_next(self.own)
                if claim is not None:
                    self._begin(claim, mono_start)
            if (
                self.active is not None
                and now - self._last_expiry_scan >= self.config.expiry_scan_s
            ):
                self._last_expiry_scan = now
                self.repo.expire_overdue()
        except OwnershipLost:
            self._on_ownership_lost()
        except QueueStorageUnavailable:
            log_event("QUEUE_STORAGE_UNAVAILABLE")

    def run_forever(self, stop: threading.Event) -> None:
        while not stop.is_set() and not self.ownership_lost and not self.closed:
            self.tick()
            time.sleep(self.config.tick_s)

    def _ownership_changed(self, now: float) -> bool:
        interval = self.config.ownership_check_s or self.profile.heartbeat_interval_s
        if now - self._last_ownership_check < interval:
            return False
        self._last_ownership_check = now
        ctl = self.repo.control()
        return not (
            ctl.supervisor_id == self.own.supervisor_id
            and ctl.generation == self.own.generation
            and ctl.state is not SupervisorState.OFFLINE
        )

    def _on_ownership_lost(self) -> None:
        """Another owner fenced us: stop our child at once and write nothing more."""
        self.ownership_lost = True
        log_event("OWNERSHIP_LOST", supervisor_id=self.supervisor_id)
        ex = self.active
        if ex is not None and ex.current is not None:
            handle = ex.current.handle
            self.driver.force_stop(handle)
            end = self.clock() + self.config.stop_confirm_timeout_s
            while self.clock() < end:
                if self.driver.poll(handle) is not None and self.driver.confirm_empty(
                    handle.identity
                ):
                    break
                self.driver.force_stop(handle)
                time.sleep(0.02)
            self.driver.dispose(handle)
        self.active = None
        self.close()

    # --- execution -----------------------------------------------------------------------------

    def _begin(self, claim: ClaimedAttempt, mono_start: float) -> None:
        registration = self.registry.get(claim.contract)
        validated = claim.input_package["input"]
        steps = registration.handler.steps(validated, self.profile)
        hard = mono_start + claim.budget_s
        self.active = Execution(
            claim=claim,
            registration=registration,
            validated=validated,
            steps=steps,
            mono_start=mono_start,
            hard_deadline=hard,
            soft_deadline=hard - self.profile.stop_grace_s,
        )
        log_event(
            "ATTEMPT_STARTED",
            job_id=claim.job_id,
            attempt_id=claim.attempt_id,
            contract=claim.contract,
            budget_s=claim.budget_s,
            steps=len(steps),
        )
        self._start_next_step(self.active)

    def _start_next_step(self, ex: Execution) -> None:
        while ex.index < len(ex.steps):
            spec = ex.steps[ex.index]
            if not should_run_step(spec, ex.outcomes):
                ex.index += 1
                continue
            elapsed = self.clock() - ex.mono_start
            window = plan_step_window(
                spec, elapsed_s=elapsed, budget_s=ex.claim.budget_s, profile=self.profile
            )
            if window is None:
                ex.outcomes.append(
                    StepOutcome(
                        spec.name,
                        StepStatus.NOT_RUN,
                        error_code=ReasonCode.PARENT_BUDGET_EXHAUSTED.value,
                        elapsed_s=round(elapsed, 3),
                    )
                )
                ex.index += 1
                continue
            envelope = {
                "input": ex.validated,
                "prior": [o.summary() for o in ex.outcomes],
                "context": {
                    "job_id": str(ex.claim.job_id),
                    "attempt_id": str(ex.claim.attempt_id),
                    "remaining_s": round(window.hard_stop_s - elapsed, 3),
                    "search_limit_s": self.profile.method_search_s,
                },
            }
            argv = [
                self.config.python,
                "-m",
                "app.workers.child",
                "--registry",
                self.config.registry_name,
                "--contract",
                ex.claim.contract,
                "--step",
                spec.name,
            ]
            try:
                handle = self.driver.start(
                    argv,
                    canonical_json(envelope).encode("utf-8"),
                    max_stdout_bytes=ex.registration.max_output_bytes,
                )
            except Exception as exc:  # noqa: BLE001 - no boundary was created
                log_event(
                    "SPAWN_FAILED", attempt_id=ex.claim.attempt_id, error_type=type(exc).__name__
                )
                self._finish(ex, failure_reason=ReasonCode.SPAWN_FAILED)
                return
            ex.current = StepRun(
                spec=spec,
                window=window,
                handle=handle,
                soft_at=ex.mono_start + window.soft_stop_s,
                force_at=ex.mono_start + window.force_stop_s,
                hard_at=ex.mono_start + window.hard_stop_s,
                started_at=self.clock(),
            )
            self.repo.record_boundary(self.own, ex.claim, handle.identity.to_json(), spec.name)
            return
        self._publish(ex)

    def _drive(self, ex: Execution, now: float) -> None:
        if ex.uncertain:
            self._reconcile(ex)
            return
        if ex.publish_pending:
            self._publish(ex)
            return
        if not ex.stopping and now - ex.last_state_poll >= self.config.state_poll_s:
            ex.last_state_poll = now
            attempt = self.repo.read_attempt(ex.claim.attempt_id)
            if attempt.state is AttemptState.STOPPING:  # cancellation recorded by the API
                self._begin_stop(ex, now)
        # Step windows already stop children by budget - reserve; this backstop must not
        # pre-empt a step's own cutoff (reserve may equal grace) and discard earlier outcomes.
        backstop = now >= ex.hard_deadline or (ex.current is None and now >= ex.soft_deadline)
        if not ex.stopping and backstop:
            self.repo.request_stop(self.own, ex.claim, ReasonCode.EXECUTION_DEADLINE_EXCEEDED)
            self._begin_stop(ex, now)
        if ex.stopping:
            self._drive_stop(ex, now)
            return
        if ex.current is None:
            self._start_next_step(ex)
            return
        self._drive_step(ex, ex.current, now)

    def _drive_step(self, ex: Execution, run: StepRun, now: float) -> None:
        driver = self.driver
        if driver.poll(run.handle) is None:
            if _overflowing(run.handle):
                run.overflowed = True
                run.kill_sent_at = run.kill_sent_at or now
                driver.force_stop(run.handle)
            elif now >= run.force_at:
                # SIGKILL a kill margin before the cutoff so the exit itself meets it.
                run.timed_out = True
                run.kill_sent_at = run.kill_sent_at or now
                driver.force_stop(run.handle)
            elif now >= run.soft_at and not run.term_sent:
                run.timed_out = run.term_sent = True
                driver.request_stop(run.handle)
            killed_long_ago = (
                run.kill_sent_at is not None
                and now >= run.kill_sent_at + self.config.stop_confirm_timeout_s
            )
            if killed_long_ago and not ex.cleanup_quarantined:
                # The leader survives SIGKILL (e.g. uninterruptible sleep): keep the slot.
                self.repo.request_stop(self.own, ex.claim, ReasonCode.CLEANUP_UNCONFIRMED)
                self._quarantine_active(ex, "STEP_KILL_UNCONFIRMED")
                self._begin_stop(ex, now)
            return
        if run.exited_at is None:
            run.exited_at = now
            run.cleanup_deadline = now + self.config.stop_confirm_timeout_s
        if not driver.confirm_empty(run.handle.identity):
            driver.force_stop(run.handle)  # members that outlived the leader
            if now >= run.cleanup_deadline and not ex.cleanup_quarantined:
                self.repo.request_stop(self.own, ex.claim, ReasonCode.CLEANUP_UNCONFIRMED)
                self._quarantine_active(ex, "STEP_CLEANUP_UNCONFIRMED")
                self._begin_stop(ex, now)
            return
        output = driver.collect(run.handle)
        driver.dispose(run.handle)
        outcome = step_outcome(
            run.spec.name,
            output,
            timed_out=run.timed_out,
            overflowed=run.overflowed,
            elapsed_s=run.exited_at - ex.mono_start,
            hard_stop_s=run.window.hard_stop_s,
        )
        if "cutoff_breach_s" in outcome.details:
            log_event(
                "STEP_CUTOFF_BREACH",
                attempt_id=ex.claim.attempt_id,
                step=run.spec.name,
                breach_s=outcome.details["cutoff_breach_s"],
            )
        log_event(
            "STEP_FINISHED",
            attempt_id=ex.claim.attempt_id,
            step=run.spec.name,
            status=outcome.status.value,
            error_code=outcome.error_code,
            elapsed_s=outcome.elapsed_s,
        )
        ex.outcomes.append(outcome)
        ex.index += 1
        ex.current = None
        self._start_next_step(ex)

    def _quarantine_active(self, ex: Execution, reason: str) -> None:
        ex.cleanup_quarantined = True
        self.quarantined = True
        self.repo.quarantine(self.own, reason)
        log_event("LANE_QUARANTINED", attempt_id=ex.claim.attempt_id, reason=reason)

    def _begin_stop(self, ex: Execution, now: float) -> None:
        if ex.stopping:
            return
        ex.stopping = True
        ex.kill_at = min(now + self.profile.stop_grace_s, max(now, ex.hard_deadline))
        if ex.current is not None and self.driver.poll(ex.current.handle) is None:
            self.driver.request_stop(ex.current.handle)

    def _drive_stop(self, ex: Execution, now: float) -> None:
        run = ex.current
        if run is not None:
            if self.driver.poll(run.handle) is None:
                if now >= ex.kill_at:
                    ex.kill_sent_at = ex.kill_sent_at or now
                    self.driver.force_stop(run.handle)
                stuck = (
                    ex.kill_sent_at is not None
                    and now >= ex.kill_sent_at + self.config.stop_confirm_timeout_s
                )
                if stuck and not ex.cleanup_quarantined:
                    self._quarantine_active(ex, "STOP_KILL_UNCONFIRMED")
                return
            if not self.driver.confirm_empty(run.handle.identity):
                self.driver.force_stop(run.handle)
                if ex.cleanup_deadline is None:
                    ex.cleanup_deadline = now + self.config.stop_confirm_timeout_s
                if now >= ex.cleanup_deadline and not ex.cleanup_quarantined:
                    self._quarantine_active(ex, "STOP_CLEANUP_UNCONFIRMED")
                return
            self.driver.dispose(run.handle)
            ex.current = None
        self._finish(ex)

    def _finish(self, ex: Execution, *, failure_reason: ReasonCode | None = None, error=None):
        """Finalize a cleaned-up non-success outcome (state from the recorded stop reason).

        An attempt already finalized elsewhere (operator attestation while local cleanup
        was pending) is left as recorded; the loop continues.
        """
        try:
            state = self.repo.finalize(
                self.own,
                ex.claim,
                failure_reason=failure_reason,
                error=error,
                diagnostics={"steps": [o.summary() for o in ex.outcomes]},
            )
            log_event("ATTEMPT_FINALIZED", attempt_id=ex.claim.attempt_id, state=state.value)
        except JobStateConflict:
            log_event("ATTEMPT_ALREADY_FINAL", attempt_id=ex.claim.attempt_id)
        self.active = None
        if ex.cleanup_quarantined:
            self._recovery_pass()

    def _timeout(self, ex: Execution) -> None:
        self.repo.request_stop(self.own, ex.claim, ReasonCode.EXECUTION_DEADLINE_EXCEEDED)
        self._finish(ex)

    def _publish(self, ex: Execution) -> None:
        ex.publish_pending = False
        if self.clock() >= ex.hard_deadline:
            self._timeout(ex)
            return
        try:
            package = ex.registration.publisher.validate(ex.validated, ex.outcomes)
        except PublicationRejected as rejected:
            if rejected.timed_out:
                self._timeout(ex)
            else:
                self._finish(
                    ex, failure_reason=reason_for(rejected.code), error={"code": rejected.code}
                )
            return
        try:
            self.repo.publish(self.own, ex.claim, package)
        except Fenced:
            attempt = self.repo.read_attempt(ex.claim.attempt_id)
            if attempt.state is AttemptState.RUNNING:
                self._timeout(ex)  # the execution deadline fenced publication
            else:
                self._finish(ex)
            return
        except PublicationRejected as rejected:
            self._finish(
                ex, failure_reason=reason_for(rejected.code), error={"code": rejected.code}
            )
            return
        except CommitUncertain:
            log_event("PUBLICATION_COMMIT_UNCERTAIN", attempt_id=ex.claim.attempt_id)
            ex.uncertain = True
            return
        except QueueStorageUnavailable:
            ex.publish_pending = True  # retried while the original deadline allows
            return
        log_event("ATTEMPT_PUBLISHED", attempt_id=ex.claim.attempt_id)
        self.active = None

    def _reconcile(self, ex: Execution) -> None:
        try:
            outcome = self.repo.reconcile_publication(self.own, ex.claim)
        except QueueStorageUnavailable:
            return  # keep the slot until the outcome is known
        log_event("PUBLICATION_RECONCILED", attempt_id=ex.claim.attempt_id, outcome=outcome)
        if outcome == "ABSENT":
            ex.uncertain = False
            self._finish(ex, failure_reason=ReasonCode.PUBLICATION_COMMIT_LOST)
        else:
            self.active = None

    # --- shutdown --------------------------------------------------------------------------

    def _wait_idle(self, timeout_s: float | None) -> None:
        budget = timeout_s if timeout_s is not None else self.profile.forecast_total_s + 30
        end = self.clock() + budget
        while self.active is not None and self.clock() < end and not self.ownership_lost:
            self.tick()
            time.sleep(self.config.tick_s)

    def shutdown_drain(self, timeout_s: float | None = None) -> None:
        """Reject new work, finish only the active attempt within its deadlines, then exit."""
        if self.own is None or self.closed:
            return
        self.draining = True
        self.repo.set_state(self.own, SupervisorState.DRAINING)
        self._wait_idle(timeout_s)
        self._release()

    def shutdown_immediate(self, timeout_s: float | None = None) -> None:
        """Stop active computation, confirm cleanup, record INTERRUPTED; keep queued work."""
        if self.own is None or self.closed:
            return
        self.draining = True
        self.repo.set_state(self.own, SupervisorState.DRAINING)
        ex = self.active
        if ex is not None and not ex.stopping:
            self.repo.request_stop(self.own, ex.claim, ReasonCode.SHUTDOWN_IMMEDIATE)
            self._begin_stop(ex, self.clock())
        self._wait_idle(timeout_s)
        self._release()

    def _release(self) -> None:
        self.pause_heartbeat()
        if self.active is None and not self.ownership_lost:
            self.repo.release(self.own)
        self.close()

    def close(self) -> None:
        """Stop background work without writing anything (also models a crash in tests)."""
        self.pause_heartbeat()
        self.closed = True

    simulate_crash = close


def main(argv: list[str] | None = None) -> int:
    from app.workers.process_driver import PosixProcessDriver
    from app.workers.registries import load_registry

    parser = argparse.ArgumentParser(description="PantryPulse compute supervisor")
    parser.add_argument("--registry", default="production", choices=["production", "test"])
    parser.add_argument("--schema", default=None, help="search_path schema (isolated tests)")
    parser.add_argument("--profile-json", default=None, help="shorter limits only")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)

    profile = PRODUCTION_PROFILE
    if args.profile_json:
        profile = RuntimeProfile(**json.loads(args.profile_json))
        if not profile.within(PRODUCTION_PROFILE):
            parser.error("profile may shorten but never exceed the accepted ceilings")
    url = os.environ.get("DATABASE_URL")
    if not url:
        parser.error("DATABASE_URL is required")
    registry = load_registry(args.registry)
    repo = QueueRepository(
        create_queue_engine(url, schema=args.schema), registry=registry, profile=profile
    )
    driver = PosixProcessDriver(cwd=API_ROOT, thread_limit=int(profile.worker_cpu))
    supervisor = Supervisor(repo, registry, driver, SupervisorConfig(args.registry, profile))
    if not supervisor.start():
        return 2
    stop = threading.Event()
    mode = {"value": "drain"}

    def on_signal(signum, _frame):
        mode["value"] = "immediate" if signum == signal.SIGINT else "drain"
        stop.set()

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)
    print(
        canonical_json({"event": "SUPERVISOR_RUNNING", "generation": supervisor.own.generation}),
        flush=True,
    )
    supervisor.run_forever(stop)
    if mode["value"] == "immediate":
        supervisor.shutdown_immediate()
    else:
        supervisor.shutdown_drain()
    return 0


if __name__ == "__main__":
    sys.exit(main())
