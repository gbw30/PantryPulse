"""PantryPulse process health and durable OR API. No startup computation."""

from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="PantryPulse API", version="0.1.0")


class HealthResponse(BaseModel):
    status: Literal["ok"]
    scope: Literal["process"]


@app.get("/api/v1/health", response_model=HealthResponse, tags=["health"])
def health() -> HealthResponse:
    """Process liveness only; does not assert database or solver readiness."""
    return HealthResponse(status="ok", scope="process")


# OR-DEC-014/020 [PROVISIONAL]: explicit presenter/simulated publication boundary.
from app.routers.or_api import router as or_router  # noqa: E402
from app.services.or_http_errors import install_or_http  # noqa: E402

install_or_http(app)
app.include_router(or_router)
