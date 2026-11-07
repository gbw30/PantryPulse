"""Rolling-origin backtest (W3-F02) and its read (W3-F03).

W0-08 stub: frozen signatures; the owning lane task replaces each body."""

from collections.abc import Callable, Sequence
from decimal import Decimal
from uuid import UUID

from app.schemas.v1_networks import BacktestResult, BacktestScore
from app.services.v1_errors import NotImplementedV1


def backtest_series(
    history: Sequence[Decimal | None], fit: Callable, origins: int = 4, horizon: int = 7
) -> BacktestScore:
    raise NotImplementedV1("W3-F02")


def get_backtest(rt, scope, job_id: UUID) -> BacktestResult:
    raise NotImplementedV1("W3-F03")
