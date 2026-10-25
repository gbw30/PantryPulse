"""VP plan/review extensions over main's canonical immutable planning records."""

from typing import Any, Literal
from uuid import UUID

import sqlalchemy as sa
from fastapi import APIRouter, Response

from app.models import or_records as legacy
from app.models.optimization import (
    MethodVerification,
    PlanningComparison,
    PlanningPlan,
    PlanningScenario,
)
from app.repositories import planning, plans
from app.repositories.forecast_history import HistoryRejected
from app.repositories.operations_api import wire
from app.routers.forecasts import PRESENTER, RUNTIME
from app.routers.operations import Key, saved_write
from app.routers.optimization import submit as submit_comparison
from app.schemas.forecast_api import ForecastAccepted
from app.schemas.plans_api import (
    AllocationResults,
    PairSubmit,
    PlanResult,
    PlanSubmit,
    ReviewRequest,
    comparison_request,
)
from app.services.optimization.decisions import DECISION_IDS
from app.services.optimization.settings import solver_settings

router = APIRouter(prefix="/api/v1", tags=["allocation"])


@router.get("/allocation-methodology")
def methodology(scope=PRESENTER):
    return dict(
        methods=["CLASSICAL_GP", "EGP_PI_INSPIRED"],
        transfer_modes=["HUB_ONLY", "HUB_AND_PANTRY"],
        default_transfer_mode=None,
        decision_ids=DECISION_IDS,
        expiry="usable through stated local expiry date",
        search_seconds=dict(default=120, maximum=300),
        donor_protection_days=7,
        planning_window_days=[1, 2, 3],
        stock_effect="NONE_SIMULATION_ONLY",
        limitations=[
            "Fixed route loading order restricts the feasible region",
            "Editable simulated policy; no real-world validity claim",
        ],
    )


def selected_scenario(rt, scope, identity, expected_hash):
    with (
        rt.engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn,
        conn.begin(),
    ):
        value = planning.read_scenario(conn, scope.organization_id, identity)
        if value["payload"].operational_hash != expected_hash:
            raise HistoryRejected("SCENARIO_REVISION_MISMATCH", 409)
        return value


@router.post("/scenarios/{scenario_id}/plans", response_model=ForecastAccepted, status_code=202)
def submit_plan(
    scenario_id: UUID,
    body: PlanSubmit,
    response: Response,
    idempotency_key: Key,
    rt=RUNTIME,
    scope=PRESENTER,
):
    saved = selected_scenario(rt, scope, scenario_id, body.expected_scenario_hash)
    accepted = rt.queue.submit(
        scope,
        "or-allocation.v2",
        dict(
            scenario_id=str(scenario_id),
            scenario=saved["payload"].model_dump(mode="json"),
            settings=solver_settings(body.search_seconds),
            method=body.method.value,
        ),
        idempotency_key,
        deduplicate=True,
    )
    status_url = f"/api/v1/jobs/{accepted.job_id}"
    response.headers["Location"] = status_url
    return ForecastAccepted(
        job_id=accepted.job_id,
        attempt_id=accepted.attempt_id,
        state=accepted.state,
        replayed=accepted.replayed,
        status_url=status_url,
        result_url=f"/api/v1/allocation-jobs/{accepted.job_id}/results",
    )


@router.post(
    "/scenarios/{scenario_id}/compare-methods", response_model=ForecastAccepted, status_code=202
)
def compare(
    scenario_id: UUID,
    body: PairSubmit,
    response: Response,
    idempotency_key: Key,
    rt=RUNTIME,
    scope=PRESENTER,
):
    selected_scenario(rt, scope, scenario_id, body.expected_scenario_hash)
    return submit_comparison(
        comparison_request(scenario_id, body), response, idempotency_key, rt, scope
    )


@router.get("/scenarios")
def scenarios(rt=RUNTIME, scope=PRESENTER):
    with (
        rt.engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn,
        conn.begin(),
    ):
        rows = (
            conn.execute(
                sa.select(PlanningScenario.id)
                .where(
                    PlanningScenario.organization_id == scope.organization_id,
                )
                .order_by(PlanningScenario.recorded_at.desc(), PlanningScenario.id)
                .limit(51)
            )
            .scalars()
            .all()
        )
        return dict(
            scenarios=[
                planning.read_scenario(conn, scope.organization_id, identity)
                for identity in rows[:50]
            ],
            more_available=len(rows) > 50,
            catalog_url="/api/v1/planning-catalog",
        )


@router.get("/plans/{record_id}", response_model=PlanResult)
def plan_read(record_id: UUID, rt=RUNTIME, scope=PRESENTER):
    with (
        rt.engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn,
        conn.begin(),
    ):
        return plans.read_plan(conn, scope.organization_id, record_id)


@router.get("/allocation-jobs/{job_id}/results", response_model=AllocationResults)
def allocation_results(job_id: UUID, rt=RUNTIME, scope=PRESENTER):
    job = rt.queue.get_job(scope, job_id)
    if job.handler_contract not in {"or-allocation.v2", "or-comparison.v2"}:
        raise HistoryRejected("ALLOCATION_JOB_NOT_FOUND", 404)
    with (
        rt.engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn,
        conn.begin(),
    ):
        ids = set(
            conn.scalars(
                sa.select(PlanningPlan.id).where(
                    PlanningPlan.organization_id == scope.organization_id,
                    PlanningPlan.job_id == job_id,
                )
            )
        )
        ids.update(
            conn.scalars(
                sa.select(MethodVerification.id)
                .join(
                    PlanningComparison,
                    sa.and_(
                        PlanningComparison.id == MethodVerification.comparison_id,
                        PlanningComparison.organization_id == MethodVerification.organization_id,
                    ),
                )
                .where(
                    MethodVerification.organization_id == scope.organization_id,
                    MethodVerification.outcome == "VERIFIED",
                    PlanningComparison.job_id == job_id,
                )
            )
        )
        comparison_id = conn.scalar(
            sa.select(PlanningComparison.id).where(
                PlanningComparison.organization_id == scope.organization_id,
                PlanningComparison.job_id == job_id,
            )
        )
        return dict(
            state=job.state,
            plans=[
                plans.read_plan(conn, scope.organization_id, identity)
                for identity in sorted(ids, key=str)
            ],
            comparison_id=comparison_id,
        )


@router.post("/plans/{plan_id}/review", status_code=201)
def review(plan_id: UUID, body: ReviewRequest, idempotency_key: Key, rt=RUNTIME, scope=PRESENTER):
    return saved_write(
        rt,
        scope,
        f"plan-review:{plan_id}",
        idempotency_key,
        body,
        lambda session: plans.review_plan(session, scope, plan_id, body),
    )


@router.get("/legacy-planning/{kind}/{record_id}")
def legacy_record(
    kind: Literal["scenarios", "plans", "comparisons"], record_id: UUID, rt=RUNTIME, scope=PRESENTER
) -> dict[str, Any]:
    # Legacy hashes/contracts retain their original family; never parse/relabel them
    # as the current v2 model or admit them directly to the production worker.
    model = {
        "scenarios": legacy.ScenarioRecord,
        "plans": legacy.PlanRecord,
        "comparisons": legacy.ComparisonRecord,
    }[kind]
    with rt.engine.connect() as conn:
        row = planning.owned_row(conn, model, scope.organization_id, record_id)
        return dict(
            contract_family="VP_LEGACY", executable=False, historical=True, record=wire(dict(row))
        )
