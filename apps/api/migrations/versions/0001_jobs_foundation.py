"""Jobs-only foundation: lane control, jobs, attempts, commands and audit (WQ-02).

No domain tables. Cross-table invariants (two waiters, lock order, fencing) are enforced by
the queue repository's locked transactions; these constraints are additional guards.

Revision ID: 0001_jobs_foundation
Revises:
Create Date: 2026-10-24
"""

from alembic import op

revision = "0001_jobs_foundation"
down_revision = None
branch_labels = None
depends_on = None

ATTEMPT_STATES = (
    "'QUEUED','RUNNING','STOPPING','SUCCEEDED','FAILED','TIMED_OUT','INTERRUPTED',"
    "'CANCELLED','EXPIRED'"
)
TERMINAL = "'SUCCEEDED','FAILED','TIMED_OUT','INTERRUPTED','CANCELLED','EXPIRED'"
SUPERVISOR_STATES = "'OFFLINE','STARTING','READY','DRAINING','RECOVERING','QUARANTINED'"
CODE = "'^[A-Z][A-Z0-9_]{0,63}$'"
HEX64 = "'^[0-9a-f]{64}$'"

UPGRADE = f"""
CREATE TABLE compute_control (
    lane_id text PRIMARY KEY CHECK (lane_id ~ '^[a-z][a-z0-9_]{{0,31}}$'),
    supervisor_id uuid,
    generation bigint NOT NULL DEFAULT 0 CHECK (generation >= 0),
    host_identity text CHECK (host_identity IS NULL OR length(host_identity) <= 512),
    state text NOT NULL DEFAULT 'OFFLINE' CHECK (state IN ({SUPERVISOR_STATES})),
    heartbeat_at timestamptz,
    active_attempt_id uuid UNIQUE,
    recovery_required boolean NOT NULL DEFAULT false,
    effective_limits jsonb NOT NULL DEFAULT '{{}}'::jsonb
        CHECK (jsonb_typeof(effective_limits) = 'object'),
    updated_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    CHECK (state = 'OFFLINE' OR supervisor_id IS NOT NULL)
);

CREATE TABLE compute_jobs (
    job_id uuid PRIMARY KEY,
    lane_id text NOT NULL REFERENCES compute_control (lane_id),
    organization_id uuid NOT NULL,
    requested_by_ref text NOT NULL CHECK (length(requested_by_ref) BETWEEN 1 AND 200),
    operation_kind text NOT NULL CHECK (operation_kind IN ('FORECAST','ALLOCATION','COMPARISON')),
    handler_contract text NOT NULL CHECK (length(handler_contract) BETWEEN 1 AND 200),
    input_schema_version text NOT NULL CHECK (length(input_schema_version) BETWEEN 1 AND 100),
    input_package jsonb NOT NULL CHECK (jsonb_typeof(input_package) = 'object'),
    input_sha256 text NOT NULL CHECK (input_sha256 ~ {HEX64}),
    current_attempt_id uuid NOT NULL,
    state text NOT NULL CHECK (state IN ({ATTEMPT_STATES})),
    created_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL,
    CHECK (updated_at >= created_at),
    UNIQUE (job_id, lane_id, organization_id)
);
CREATE INDEX ix_compute_jobs_organization ON compute_jobs (organization_id, created_at);

CREATE TABLE compute_attempts (
    attempt_id uuid PRIMARY KEY,
    job_id uuid NOT NULL,
    attempt_number integer NOT NULL CHECK (attempt_number > 0),
    lane_id text NOT NULL,
    organization_id uuid NOT NULL,
    state text NOT NULL CHECK (state IN ({ATTEMPT_STATES})),
    reason_code text CHECK (reason_code IS NULL OR reason_code ~ {CODE}),
    state_version bigint NOT NULL DEFAULT 0 CHECK (state_version >= 0),
    enqueued_at timestamptz NOT NULL,
    queue_deadline_at timestamptz NOT NULL,
    supervisor_id uuid,
    supervisor_generation bigint CHECK (supervisor_generation IS NULL OR supervisor_generation > 0),
    execution_token uuid,
    started_at timestamptz,
    execution_deadline_at timestamptz,
    primary_deadline_at timestamptz,
    current_phase text CHECK (current_phase IS NULL OR length(current_phase) <= 64),
    execution_boundary jsonb CHECK (
        execution_boundary IS NULL OR jsonb_typeof(execution_boundary) = 'object'),
    stop_requested_at timestamptz,
    stop_reason text CHECK (stop_reason IS NULL OR stop_reason ~ {CODE}),
    cleanup_confirmed_at timestamptz,
    diagnostics jsonb NOT NULL DEFAULT '{{}}'::jsonb CHECK (jsonb_typeof(diagnostics) = 'object'),
    completed_at timestamptz,
    result_manifest jsonb CHECK (
        result_manifest IS NULL OR jsonb_typeof(result_manifest) = 'object'),
    error jsonb CHECK (error IS NULL OR jsonb_typeof(error) = 'object'),
    UNIQUE (job_id, attempt_number),
    UNIQUE (job_id, attempt_id),
    UNIQUE (lane_id, attempt_id),
    FOREIGN KEY (job_id, lane_id, organization_id)
        REFERENCES compute_jobs (job_id, lane_id, organization_id) DEFERRABLE INITIALLY DEFERRED,
    CHECK (queue_deadline_at > enqueued_at),
    CHECK ((supervisor_id IS NULL) = (execution_token IS NULL)
        AND (supervisor_id IS NULL) = (supervisor_generation IS NULL)
        AND (supervisor_id IS NULL) = (started_at IS NULL)
        AND (supervisor_id IS NULL) = (execution_deadline_at IS NULL)),
    CHECK (execution_deadline_at IS NULL OR execution_deadline_at > started_at),
    CHECK (started_at IS NULL OR started_at >= enqueued_at),
    CHECK (primary_deadline_at IS NULL OR (started_at IS NOT NULL
        AND primary_deadline_at > started_at AND primary_deadline_at <= execution_deadline_at)),
    CHECK (state NOT IN ('RUNNING','STOPPING','SUCCEEDED','TIMED_OUT','INTERRUPTED')
        OR started_at IS NOT NULL),
    CHECK (state <> 'QUEUED' OR (started_at IS NULL AND stop_requested_at IS NULL)),
    CHECK ((state IN ({TERMINAL})) = (completed_at IS NOT NULL)),
    CHECK (completed_at IS NULL OR completed_at >= enqueued_at),
    CHECK ((state = 'SUCCEEDED') = (result_manifest IS NOT NULL)),
    CHECK (state NOT IN ('FAILED','TIMED_OUT','INTERRUPTED','CANCELLED','EXPIRED')
        OR reason_code IS NOT NULL),
    CHECK (state <> 'STOPPING' OR stop_requested_at IS NOT NULL),
    CHECK ((stop_requested_at IS NULL) = (stop_reason IS NULL)),
    CHECK (state NOT IN ({TERMINAL}) OR started_at IS NULL OR cleanup_confirmed_at IS NOT NULL)
);
CREATE UNIQUE INDEX uq_compute_attempts_active_per_lane
    ON compute_attempts (lane_id) WHERE state IN ('RUNNING','STOPPING');
CREATE UNIQUE INDEX uq_compute_attempts_nonterminal_per_job
    ON compute_attempts (job_id) WHERE state IN ('QUEUED','RUNNING','STOPPING');
CREATE INDEX ix_compute_attempts_queue
    ON compute_attempts (lane_id, state, enqueued_at, attempt_id);
CREATE INDEX ix_compute_attempts_organization ON compute_attempts (organization_id, job_id);

ALTER TABLE compute_jobs ADD CONSTRAINT fk_compute_jobs_current_attempt
    FOREIGN KEY (job_id, current_attempt_id) REFERENCES compute_attempts (job_id, attempt_id)
    DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE compute_control ADD CONSTRAINT fk_compute_control_active_attempt
    FOREIGN KEY (lane_id, active_attempt_id) REFERENCES compute_attempts (lane_id, attempt_id);

CREATE TABLE compute_commands (
    command_id uuid PRIMARY KEY,
    organization_id uuid NOT NULL,
    action text NOT NULL CHECK (action IN ('SUBMIT','RETRY','CANCEL')),
    idempotency_key text NOT NULL CHECK (idempotency_key ~ '^[A-Za-z0-9._:-]{{1,128}}$'),
    request_sha256 text NOT NULL CHECK (request_sha256 ~ {HEX64}),
    job_id uuid NOT NULL REFERENCES compute_jobs (job_id),
    attempt_id uuid REFERENCES compute_attempts (attempt_id),
    response jsonb NOT NULL CHECK (jsonb_typeof(response) = 'object'),
    created_at timestamptz NOT NULL,
    UNIQUE (organization_id, action, idempotency_key)
);

CREATE TABLE compute_audit_events (
    event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    lane_id text NOT NULL,
    job_id uuid,
    attempt_id uuid,
    event_type text NOT NULL CHECK (event_type ~ {CODE}),
    from_state text,
    to_state text,
    supervisor_id uuid,
    supervisor_generation bigint,
    reason_code text CHECK (reason_code IS NULL OR reason_code ~ {CODE}),
    details jsonb NOT NULL DEFAULT '{{}}'::jsonb CHECK (jsonb_typeof(details) = 'object')
);
CREATE INDEX ix_compute_audit_events_job ON compute_audit_events (job_id, event_id);

CREATE FUNCTION compute_jobs_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF NEW.job_id IS DISTINCT FROM OLD.job_id
       OR NEW.lane_id IS DISTINCT FROM OLD.lane_id
       OR NEW.organization_id IS DISTINCT FROM OLD.organization_id
       OR NEW.requested_by_ref IS DISTINCT FROM OLD.requested_by_ref
       OR NEW.operation_kind IS DISTINCT FROM OLD.operation_kind
       OR NEW.handler_contract IS DISTINCT FROM OLD.handler_contract
       OR NEW.input_schema_version IS DISTINCT FROM OLD.input_schema_version
       OR NEW.input_package IS DISTINCT FROM OLD.input_package
       OR NEW.input_sha256 IS DISTINCT FROM OLD.input_sha256
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'compute job identity and input are immutable'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER trg_compute_jobs_guard BEFORE UPDATE ON compute_jobs
    FOR EACH ROW EXECUTE FUNCTION compute_jobs_guard();

CREATE FUNCTION compute_attempts_guard() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.state IN ({TERMINAL}) THEN
        RAISE EXCEPTION 'terminal compute attempt % is immutable', OLD.attempt_id
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    IF NEW.attempt_id IS DISTINCT FROM OLD.attempt_id
       OR NEW.job_id IS DISTINCT FROM OLD.job_id
       OR NEW.attempt_number IS DISTINCT FROM OLD.attempt_number
       OR NEW.lane_id IS DISTINCT FROM OLD.lane_id
       OR NEW.organization_id IS DISTINCT FROM OLD.organization_id
       OR NEW.enqueued_at IS DISTINCT FROM OLD.enqueued_at
       OR NEW.queue_deadline_at IS DISTINCT FROM OLD.queue_deadline_at
       OR (OLD.started_at IS NOT NULL AND (
            NEW.supervisor_id IS DISTINCT FROM OLD.supervisor_id
            OR NEW.supervisor_generation IS DISTINCT FROM OLD.supervisor_generation
            OR NEW.execution_token IS DISTINCT FROM OLD.execution_token
            OR NEW.started_at IS DISTINCT FROM OLD.started_at
            OR NEW.execution_deadline_at IS DISTINCT FROM OLD.execution_deadline_at
            OR NEW.primary_deadline_at IS DISTINCT FROM OLD.primary_deadline_at))
       OR (OLD.stop_requested_at IS NOT NULL AND (
            NEW.stop_requested_at IS DISTINCT FROM OLD.stop_requested_at
            OR NEW.stop_reason IS DISTINCT FROM OLD.stop_reason)) THEN
        RAISE EXCEPTION 'compute attempt identity, claim and stop fields are immutable'
            USING ERRCODE = 'integrity_constraint_violation';
    END IF;
    IF NEW.state IS DISTINCT FROM OLD.state THEN
        IF NOT ((OLD.state = 'QUEUED' AND NEW.state IN ('RUNNING','CANCELLED','EXPIRED','FAILED'))
             OR (OLD.state = 'RUNNING' AND NEW.state IN ('SUCCEEDED','FAILED','STOPPING'))
             OR (OLD.state = 'STOPPING'
                 AND NEW.state IN ('FAILED','TIMED_OUT','INTERRUPTED','CANCELLED'))) THEN
            RAISE EXCEPTION 'compute attempt transition % -> % is not allowed',
                OLD.state, NEW.state USING ERRCODE = 'integrity_constraint_violation';
        END IF;
        IF NEW.state_version <> OLD.state_version + 1 THEN
            RAISE EXCEPTION 'compute attempt state change must advance state_version by one'
                USING ERRCODE = 'integrity_constraint_violation';
        END IF;
    END IF;
    RETURN NEW;
END $$;
CREATE TRIGGER trg_compute_attempts_guard BEFORE UPDATE ON compute_attempts
    FOR EACH ROW EXECUTE FUNCTION compute_attempts_guard();

CREATE FUNCTION compute_audit_events_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'compute audit events are append-only'
        USING ERRCODE = 'integrity_constraint_violation';
END $$;
CREATE TRIGGER trg_compute_audit_events_append_only BEFORE UPDATE OR DELETE
    ON compute_audit_events FOR EACH ROW EXECUTE FUNCTION compute_audit_events_append_only();

INSERT INTO compute_control (lane_id) VALUES ('default');
"""

DOWNGRADE = """
DROP TABLE compute_audit_events;
DROP TABLE compute_commands;
ALTER TABLE compute_control DROP CONSTRAINT fk_compute_control_active_attempt;
ALTER TABLE compute_jobs DROP CONSTRAINT fk_compute_jobs_current_attempt;
DROP TABLE compute_attempts;
DROP TABLE compute_jobs;
DROP TABLE compute_control;
DROP FUNCTION compute_audit_events_append_only();
DROP FUNCTION compute_attempts_guard();
DROP FUNCTION compute_jobs_guard();
"""


def upgrade() -> None:
    op.execute(UPGRADE)


def downgrade() -> None:
    op.execute(DOWNGRADE)
