"""forecast_runs stores each run's backtest (CR-w3-forecast-1 option B, Gabriel 2026-11-09).

GET /forecasts/{job_id}/backtest serves one run's BacktestResult. The forecast.v1 network publisher
writes its body ({series, locations, ineligible}, keyed by CSV ids) in the run's INSERT, so it is
immutable with the run. Older runs and v2 site runs keep NULL. backtest_scores stays unused.

Downgrade refuses while any run has a stored backtest: it would be lost.
"""

import sqlalchemy as sa
from alembic import op

revision = "ppv1_0014"
down_revision = "ppv1_0013"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE forecast_runs ADD COLUMN backtest JSONB, "
               "ADD CONSTRAINT ck_forecast_runs_backtest "
               "CHECK (backtest IS NULL OR jsonb_typeof(backtest) = 'object')")


def downgrade():
    if op.get_bind().scalar(sa.text(
            "SELECT EXISTS (SELECT 1 FROM forecast_runs WHERE backtest IS NOT NULL)")):
        raise RuntimeError("V1_DATA_PRESENT: forecast runs with a stored backtest would lose it")
    op.execute("ALTER TABLE forecast_runs DROP COLUMN backtest")  # drops its check too
