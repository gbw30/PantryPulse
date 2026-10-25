"""Verified method records and append-only simulation reviews; never mutate stock."""

from uuid import uuid4

import sqlalchemy as sa

from app.models.optimization import (
    MethodVerification,
    PlanningComparison,
    PlanningPlan,
    PlanningReview,
)
from app.repositories import planning
from app.repositories.forecast_history import HistoryRejected
from app.services.jobs.contracts import sha256_hex


def put_plan(conn, identity, scenario_id, settings, result, *, comparison_id=None, plan_id=None):
    if result["outcome"] != "VERIFIED" or not result["verification"]["passed"]:
        raise ValueError("UNVERIFIED_PLAN")
    plan_id = plan_id or uuid4()
    conn.execute(
        sa.insert(PlanningPlan).values(
            id=plan_id,
            organization_id=identity.organization_id,
            scenario_id=scenario_id,
            job_id=identity.job_id,
            attempt_id=identity.attempt_id,
            comparison_id=comparison_id,
            method=result["method"],
            settings=settings,
            result=result,
            result_hash=sha256_hex(result),
        )
    )
    return plan_id


def plan_row(conn, org, identity):
    row = (
        conn.execute(
            sa.select(PlanningPlan.__table__).where(
                PlanningPlan.organization_id == org,
                PlanningPlan.id == identity,
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        # Comparisons saved before this extension already own immutable method
        # records. Expose those exact records without rewriting historical evidence.
        item = (
            conn.execute(
                sa.select(
                    MethodVerification.id,
                    MethodVerification.method,
                    MethodVerification.record,
                    MethodVerification.recorded_at,
                    PlanningComparison.scenario_id,
                    PlanningComparison.job_id,
                    PlanningComparison.attempt_id,
                    PlanningComparison.settings,
                    PlanningComparison.id.label("comparison_id"),
                )
                .join(
                    PlanningComparison,
                    sa.and_(
                        PlanningComparison.id == MethodVerification.comparison_id,
                        PlanningComparison.organization_id == MethodVerification.organization_id,
                    ),
                )
                .where(
                    MethodVerification.id == identity,
                    MethodVerification.organization_id == org,
                    MethodVerification.outcome == "VERIFIED",
                )
            )
            .mappings()
            .one_or_none()
        )
        if item is None:
            raise HistoryRejected("PLAN_NOT_FOUND", 404)
        row = {key: value for key, value in item.items() if key != "record"}
        row.update(
            organization_id=org, result=item["record"], result_hash=sha256_hex(item["record"])
        )
    if sha256_hex(row["result"]) != row["result_hash"]:
        raise HistoryRejected("PLAN_INTEGRITY_FAILED", 409)
    return dict(row)


def read_plan(conn, org, identity):
    row = plan_row(conn, org, identity)
    scenario = planning.read_scenario(conn, org, row["scenario_id"])
    return {key: value for key, value in row.items() if key != "organization_id"} | dict(
        stale=scenario["stale"],
        historical=scenario["historical"],
    )


def review_plan(session, scope, identity, body):
    conn = session.connection()
    row = plan_row(conn, scope.organization_id, identity)
    if row["result_hash"] != body.expected_result_hash:
        raise HistoryRejected("PLAN_REVISION_MISMATCH", 409)
    if conn.scalar(sa.select(PlanningPlan.id).where(PlanningPlan.id == identity)) is None:
        conn.execute(sa.insert(PlanningPlan).values(**row))
    review_id = uuid4()
    conn.execute(
        sa.insert(PlanningReview).values(
            id=review_id,
            organization_id=scope.organization_id,
            plan_id=identity,
            actor=scope.actor_ref,
            action=body.action,
            result_hash=row["result_hash"],
            note=body.note,
        )
    )
    return dict(
        conn.execute(
            sa.select(PlanningReview.__table__).where(
                PlanningReview.id == review_id,
            )
        )
        .mappings()
        .one()
    )
