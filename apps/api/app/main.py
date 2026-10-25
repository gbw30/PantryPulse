"""Application scaffold. Domain endpoints are intentionally not implemented."""

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
