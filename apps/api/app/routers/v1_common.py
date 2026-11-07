"""Shared pieces of the thin v1 routers: auth, idempotency key and the error responses."""

from typing import Annotated

from fastapi import Header

from app.routers.forecasts import PRESENTER, RUNTIME
from app.schemas.forecast_api import ErrorEnvelope

__all__ = ["KEY", "PRESENTER", "RESPONSES", "RUNTIME", "job_accepted"]

KEY = Annotated[str, Header(min_length=1, max_length=128)]
RESPONSES = {
    code: {"model": ErrorEnvelope} for code in (401, 403, 404, 409, 413, 422, 501, 503)
}


def job_accepted(response, accepted):
    """202 with the job's status URL in Location, as the v2 job routes do."""
    response.headers["Location"] = accepted.status_url
    return accepted
