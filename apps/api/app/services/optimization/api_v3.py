"""Router-facing v1 comparisons: submit or-comparison.v3, read, actions, export (W1-S04/S06/S07).

comparison_id = job_id. The comparison row is written in the same transaction that marks the
attempt SUCCEEDED, so every read before publication is 404 COMPARISON_NOT_FOUND.

Tenancy (W0-network-model 1-2): each network has its own organization. The local session may use
every network of the install; each request is authorized against the network in its path and
runs under that network's organization, never one sent by the client."""

from collections.abc import Sequence
from uuid import UUID

import sqlalchemy as sa

from app.models.networks import PlanningComparisonV3, PlanningScenarioV3
from app.repositories.forecast_history import HistoryRejected
from app.repositories.networks import network_scope
from app.schemas.forecast_api import ForecastAccepted
from app.schemas.v1_planning import (
    AllocationMethod,
    ComparisonRequestV3,
    DecisionActions,
    ORInputV3,
    SavedComparisonV3,
)


def _scenario(conn, scope, network_id, scenario_id):
    row = (
        conn.execute(
            sa.select(PlanningScenarioV3.__table__).where(
                PlanningScenarioV3.id == scenario_id,
                PlanningScenarioV3.organization_id == scope.organization_id,
                PlanningScenarioV3.network_id == network_id,
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HistoryRejected("SCENARIO_NOT_FOUND", 404)
    return row


def _read(rt, scope, network_id, comparison_id):
    """The saved comparison and its frozen scenario, read in one snapshot."""
    with (
        rt.engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn,
        conn.begin(),
    ):
        scope = network_scope(conn, scope, network_id)
        row = (
            conn.execute(
                sa.select(PlanningComparisonV3.__table__).where(
                    PlanningComparisonV3.id == comparison_id,
                    PlanningComparisonV3.organization_id == scope.organization_id,
                    PlanningComparisonV3.network_id == network_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None:
            raise HistoryRejected("COMPARISON_NOT_FOUND", 404)
        scenario = _scenario(conn, scope, network_id, row["scenario_id"])
    frozen = ORInputV3.model_validate(scenario["payload"])
    saved = SavedComparisonV3(
        id=row["id"],
        network_id=row["network_id"],
        scenario_id=row["scenario_id"],
        recorded_at=row["recorded_at"],
        result=row["result"],
        assumptions=frozen.assumptions,  # copied from the frozen scenario (CR-w1-web-6)
        inbound_file_provided=frozen.inbound_file_provided,
    )
    return saved, frozen


def submit_comparison(
    rt, scope, network_id: UUID, request: ComparisonRequestV3, idempotency_key: str
) -> ForecastAccepted:
    """Checks the methods against the scenario's mode with require_methods_for_mode (422)."""
    with (
        rt.engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn,
        conn.begin(),
    ):
        scope = network_scope(conn, scope, network_id)
        scenario = _scenario(conn, scope, network_id, request.scenario_id)
    accepted = rt.queue.submit(
        scope,
        "or-comparison.v3",
        dict(
            network_id=str(network_id),
            scenario_id=str(request.scenario_id),
            scenario_hash=scenario["content_hash"],
            scenario=scenario["payload"],
            methods=list(request.methods),
            measure=request.measure,
        ),
        idempotency_key,
        deduplicate=True,
    )
    return ForecastAccepted(
        job_id=accepted.job_id,
        attempt_id=accepted.attempt_id,
        state=accepted.state,
        replayed=accepted.replayed,
        status_url=f"/api/v1/jobs/{accepted.job_id}",
        result_url=f"/api/v1/networks/{network_id}/comparisons/{accepted.job_id}",
    )


def get_comparison(rt, scope, network_id: UUID, comparison_id: UUID) -> SavedComparisonV3:
    return _read(rt, scope, network_id, comparison_id)[0]


def _method(saved, method):
    chosen = next((m for m in saved.result.methods if m.method == method), None)
    if chosen is None:
        raise HistoryRejected("METHOD_NOT_IN_COMPARISON", 404)
    if not chosen.verified:
        raise HistoryRejected("RESULT_NOT_VERIFIED", 409)
    return chosen


def comparison_actions(
    rt, scope, network_id: UUID, comparison_id: UUID, method: AllocationMethod
) -> DecisionActions:
    from app.services.optimization.actions import decision_actions

    saved, scenario = _read(rt, scope, network_id, comparison_id)
    return decision_actions(scenario, _method(saved, method), comparison_id=saved.id)


def export_comparison(
    rt,
    scope,
    network_id: UUID,
    comparison_id: UUID,
    method: AllocationMethod,
    action_ids: Sequence[str],
) -> str:
    from app.services.optimization.export import export_plan_csv

    saved, scenario = _read(rt, scope, network_id, comparison_id)
    planned = {t.id for t in _method(saved, method).transfers}  # action id = transfer id
    if not set(action_ids) <= planned:
        raise HistoryRejected("UNKNOWN_ACTION_ID", 422)
    return export_plan_csv(saved, method, action_ids, scenario=scenario)
