"""Draft-1 PostgreSQL records. These are planning snapshots, never a stock ledger.

OR-DEC-012 [PROVISIONAL]: immutable JSONB records own OR persistence only.
OR-DEC-011 [PROVISIONAL]: one shared compute control row owns expensive work.
"""

from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.models.jobs import compute_attempts, compute_jobs, metadata

# Composite scopes extend the shared queue tables without replacing their owner.
compute_jobs.append_constraint(
    UniqueConstraint("organization_id", "job_id", name="uq_compute_job_org_id")
)
compute_attempts.append_constraint(
    UniqueConstraint("organization_id", "attempt_id", name="uq_compute_attempt_org_id")
)


class Base(DeclarativeBase):
    metadata = metadata


class Identity:
    id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)


class Created:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("clock_timestamp()")
    )


class DatasetState(Base):
    __tablename__ = "or_dataset_state"
    organization_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    dataset_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), primary_key=True)
    revision_token: Mapped[str] = mapped_column(String(256), nullable=False)
    org_epoch: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    __table_args__ = (CheckConstraint("org_epoch >= 0", name="ck_dataset_epoch"),)


class InputPackageRecord(Identity, Created, Base):
    __tablename__ = "or_input_packages"
    dataset_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    source_kind: Mapped[str] = mapped_column(String(16), nullable=False)
    revision_token: Mapped[str] = mapped_column(String(256), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    source_manifest_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_or_package_org_id"),
        UniqueConstraint(
            "organization_id", "dataset_id", "content_hash", name="uq_or_package_content"
        ),
        CheckConstraint("source_kind IN ('SIMULATED','LIVE')", name="ck_or_package_source"),
        CheckConstraint("content_hash ~ '^[0-9a-f]{64}$'", name="ck_or_package_hash"),
        CheckConstraint("source_manifest_hash ~ '^[0-9a-f]{64}$'", name="ck_or_manifest_hash"),
        CheckConstraint("jsonb_typeof(payload) = 'object'", name="ck_or_package_payload"),
    )


class PolicyRecord(Identity, Created, Base):
    __tablename__ = "or_policies"
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    decision_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    created_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_or_policy_org_id"),
        UniqueConstraint("organization_id", "content_hash", name="uq_or_policy_content"),
        CheckConstraint("content_hash ~ '^[0-9a-f]{64}$'", name="ck_or_policy_hash"),
        CheckConstraint("jsonb_typeof(payload) = 'object'", name="ck_or_policy_payload"),
        CheckConstraint("jsonb_typeof(decision_ids) = 'array'", name="ck_or_policy_decisions"),
    )


class ScenarioRecord(Identity, Created, Base):
    __tablename__ = "or_scenarios"
    input_package_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    policy_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(64), nullable=False)
    transfer_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    planning_days: Mapped[int] = mapped_column(Integer, nullable=False)
    intent: Mapped[str] = mapped_column(String(32), nullable=False)
    revision_token: Mapped[str] = mapped_column(String(256), nullable=False)
    org_epoch: Mapped[int] = mapped_column(BigInteger, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    operational_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    policy_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_or_scenario_org_id"),
        UniqueConstraint(
            "organization_id",
            "operational_hash",
            "policy_hash",
            "org_epoch",
            name="uq_or_scenario_content",
        ),
        ForeignKeyConstraint(
            ["organization_id", "input_package_id"],
            ["or_input_packages.organization_id", "or_input_packages.id"],
            name="fk_or_scenario_package",
        ),
        ForeignKeyConstraint(
            ["organization_id", "policy_id"],
            ["or_policies.organization_id", "or_policies.id"],
            name="fk_or_scenario_policy",
        ),
        CheckConstraint("transfer_mode IN ('HUB_ONLY','HUB_AND_PANTRY')", name="ck_or_mode"),
        CheckConstraint("planning_days BETWEEN 1 AND 3", name="ck_or_window"),
        CheckConstraint("intent IN ('CURRENT','HISTORICAL_REPLAY')", name="ck_or_intent"),
        CheckConstraint("org_epoch >= 0", name="ck_or_scenario_epoch"),
        CheckConstraint("operational_hash ~ '^[0-9a-f]{64}$'", name="ck_or_operational_hash"),
        CheckConstraint("policy_hash ~ '^[0-9a-f]{64}$'", name="ck_or_scenario_policy_hash"),
        Index("ix_or_scenario_page", "organization_id", "created_at", "id"),
    )


class RequestKey(Identity, Created, Base):
    __tablename__ = "or_request_keys"
    actor_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    route_operation: Mapped[str] = mapped_column(String(128), nullable=False)
    key: Mapped[str] = mapped_column(String(256), nullable=False)
    request_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    job_or_resource_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "actor_id", "route_operation", "key", name="uq_or_request_key"
        ),
        CheckConstraint("length(key) BETWEEN 1 AND 256", name="ck_or_request_key_length"),
        CheckConstraint("request_hash ~ '^[0-9a-f]{64}$'", name="ck_or_request_hash"),
    )


class PlanRecord(Identity, Created, Base):
    __tablename__ = "or_plans"
    scenario_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    job_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    attempt_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    method: Mapped[str] = mapped_column(String(32), nullable=False)
    native_status: Mapped[str] = mapped_column(String(24), nullable=False)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    settings_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    result_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_or_plan_org_id"),
        UniqueConstraint("attempt_id", "method", name="uq_or_plan_attempt_method"),
        ForeignKeyConstraint(
            ["organization_id", "scenario_id"],
            ["or_scenarios.organization_id", "or_scenarios.id"],
            name="fk_or_plan_scenario",
        ),
        ForeignKeyConstraint(
            ["organization_id", "job_id"],
            ["compute_jobs.organization_id", "compute_jobs.job_id"],
            name="fk_or_plan_job",
        ),
        ForeignKeyConstraint(
            ["organization_id", "attempt_id"],
            ["compute_attempts.organization_id", "compute_attempts.attempt_id"],
            name="fk_or_plan_attempt",
        ),
        ForeignKeyConstraint(
            ["job_id", "attempt_id"],
            ["compute_attempts.job_id", "compute_attempts.attempt_id"],
            name="fk_or_plan_job_attempt",
        ),
        CheckConstraint("method IN ('CLASSICAL_GP','EGP_PI_INSPIRED')", name="ck_or_plan_method"),
        CheckConstraint("native_status IN ('OPTIMAL','FEASIBLE')", name="ck_or_plan_native"),
        CheckConstraint("outcome = 'VERIFIED'", name="ck_or_plan_verified"),
        CheckConstraint("result_hash ~ '^[0-9a-f]{64}$'", name="ck_or_result_hash"),
    )


class TransferRecord(Identity, Base):
    __tablename__ = "or_transfers"
    plan_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    original_lot_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    source_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    destination_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    product_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    unit: Mapped[str] = mapped_column(String(64), nullable=False)
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False)
    departure_date: Mapped[date] = mapped_column(Date, nullable=False)
    arrival_date: Mapped[date] = mapped_column(Date, nullable=False)
    expiry_date: Mapped[date] = mapped_column(Date, nullable=False)
    source_revision: Mapped[str] = mapped_column(String(256), nullable=False)
    cost_minor: Mapped[int] = mapped_column(BigInteger, nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "plan_id"],
            ["or_plans.organization_id", "or_plans.id"],
            name="fk_or_transfer_plan",
        ),
        UniqueConstraint(
            "plan_id",
            "original_lot_id",
            "source_id",
            "destination_id",
            "product_id",
            name="uq_or_transfer_lineage",
        ),
        CheckConstraint("quantity > 0 AND cost_minor >= 0", name="ck_or_transfer_amounts"),
        CheckConstraint("source_id <> destination_id", name="ck_or_transfer_no_self"),
        CheckConstraint(
            "arrival_date >= departure_date AND expiry_date > arrival_date",
            name="ck_or_transfer_dates",
        ),
    )


class VerificationRecord(Identity, Base):
    __tablename__ = "or_verifications"
    plan_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, unique=True)
    verifier_version: Mapped[str] = mapped_column(String(64), nullable=False)
    passed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    checks: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    objective: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    report_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "plan_id"],
            ["or_plans.organization_id", "or_plans.id"],
            name="fk_or_check_plan",
        ),
        CheckConstraint("passed", name="ck_or_check_passed"),
        CheckConstraint("report_hash ~ '^[0-9a-f]{64}$'", name="ck_or_check_hash"),
    )


class ComparisonRecord(Identity, Created, Base):
    __tablename__ = "or_comparisons"
    job_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    attempt_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False, unique=True)
    scenario_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    first_plan_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    second_plan_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    outcome: Mapped[str] = mapped_column(String(24), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_or_comparison_org_id"),
        ForeignKeyConstraint(
            ["organization_id", "scenario_id"],
            ["or_scenarios.organization_id", "or_scenarios.id"],
            name="fk_or_comparison_scenario",
        ),
        ForeignKeyConstraint(
            ["organization_id", "job_id"],
            ["compute_jobs.organization_id", "compute_jobs.job_id"],
            name="fk_or_comparison_job",
        ),
        ForeignKeyConstraint(
            ["organization_id", "attempt_id"],
            ["compute_attempts.organization_id", "compute_attempts.attempt_id"],
            name="fk_or_comparison_attempt",
        ),
        ForeignKeyConstraint(
            ["organization_id", "first_plan_id"],
            ["or_plans.organization_id", "or_plans.id"],
            name="fk_or_comparison_first",
        ),
        ForeignKeyConstraint(
            ["organization_id", "second_plan_id"],
            ["or_plans.organization_id", "or_plans.id"],
            name="fk_or_comparison_second",
        ),
        CheckConstraint(
            "outcome IN ('SUCCEEDED','PARTIAL','FAILED')", name="ck_or_comparison_outcome"
        ),
        CheckConstraint(
            "(outcome = 'SUCCEEDED' AND first_plan_id IS NOT NULL "
            "AND second_plan_id IS NOT NULL) OR (outcome = 'PARTIAL' AND "
            "((first_plan_id IS NULL) <> (second_plan_id IS NULL))) OR "
            "(outcome = 'FAILED' AND first_plan_id IS NULL AND second_plan_id IS NULL)",
            name="ck_or_comparison_completeness",
        ),
    )


class ReviewRecord(Identity, Created, Base):
    __tablename__ = "or_reviews"
    plan_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    actor_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    plan_result_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "plan_id"],
            ["or_plans.organization_id", "or_plans.id"],
            name="fk_or_review_plan",
        ),
        CheckConstraint("action IN ('REVIEWED','REJECTED')", name="ck_or_review_action"),
        CheckConstraint("note IS NULL OR length(note) <= 2000", name="ck_or_review_note"),
    )


class AuditEvent(Identity, Created, Base):
    __tablename__ = "audit_events"
    actor_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    action: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_id: Mapped[UUID | None] = mapped_column(PGUUID(as_uuid=True))
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)


class PresenterSession(Identity, Created, Base):
    __tablename__ = "presenter_sessions"
    actor_id: Mapped[str] = mapped_column(String(200), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    csrf_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (
        CheckConstraint(
            "token_hash ~ '^[0-9a-f]{64}$' AND csrf_hash ~ '^[0-9a-f]{64}$'",
            name="ck_presenter_hashes",
        ),
        CheckConstraint("expires_at > created_at", name="ck_presenter_expiry"),
    )
