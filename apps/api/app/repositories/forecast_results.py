"""Committed forecast handoff. Never invokes inference or rounds planning quantities."""

from uuid import UUID

import sqlalchemy as sa

from app.models.forecasts import ForecastRun
from app.models.jobs import compute_attempts, compute_jobs
from app.repositories.forecast_history import HistoryRejected
from app.services.forecasting.postprocessing import validate_output
from app.services.forecasting.preparation import validate_input
from app.services.forecasting.schemas import ForecastInput, ForecastOutput


def read_committed_forecast(engine, organization_id: UUID, run_id: UUID):
    """Planning callers receive exact frozen inputs and original raw model precision."""
    with engine.connect() as conn:
        return read_committed_forecast_connection(conn, organization_id, run_id)


def read_committed_forecast_connection(conn, organization_id: UUID, run_id: UUID):
    row = (
        conn.execute(
            sa.select(ForecastRun.__table__)
            .join(
                compute_jobs,
                sa.and_(
                    compute_jobs.c.job_id == ForecastRun.job_id,
                    compute_jobs.c.organization_id == ForecastRun.organization_id,
                ),
            )
            .join(
                compute_attempts,
                sa.and_(
                    compute_attempts.c.attempt_id == ForecastRun.attempt_id,
                    compute_attempts.c.organization_id == organization_id,
                ),
            )
            .where(
                ForecastRun.organization_id == organization_id,
                ForecastRun.id == run_id,
                compute_jobs.c.state == "SUCCEEDED",
                compute_attempts.c.state == "SUCCEEDED",
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise HistoryRejected("FORECAST_NOT_FOUND", 404)
    if not row["planning_ready"]:
        raise HistoryRejected("FORECAST_NOT_PLANNING_READY", 409)
    inputs = validate_input(ForecastInput.model_validate(row["frozen_input"]))
    output = validate_output(inputs, ForecastOutput.model_validate(row["output"]))
    if not output.ready_for_publication or output.run_id != run_id:
        raise HistoryRejected("FORECAST_INTEGRITY_FAILED", 409)
    return inputs, output
