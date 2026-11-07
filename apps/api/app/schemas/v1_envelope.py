"""v1 size envelope (V1-SPEC §5.1).

Anything over it is rejected with the limit named, never truncated.
"""

from dataclasses import dataclass

MAX_LOCATIONS = 100
MAX_PRODUCTS = 500
MAX_HISTORY_DAYS = 90
MIN_FORECAST_HISTORY_DAYS = 14
MIN_BACKTEST_HISTORY_DAYS = 35
MAX_BATCHES = 200_000
MAX_FORECAST_SERIES = 50_000
MAX_REPORTED_ERRORS = 1000
# S4: the 143 MB maximum-envelope history file plus headroom, counted while streaming.
UPLOAD_CAP_BYTES = 160 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class Envelope:
    max_locations: int = MAX_LOCATIONS
    max_products: int = MAX_PRODUCTS
    max_history_days: int = MAX_HISTORY_DAYS
    min_forecast_history_days: int = MIN_FORECAST_HISTORY_DAYS
    min_backtest_history_days: int = MIN_BACKTEST_HISTORY_DAYS
    max_batches: int = MAX_BATCHES
    max_forecast_series: int = MAX_FORECAST_SERIES
    max_reported_errors: int = MAX_REPORTED_ERRORS


V1_ENVELOPE = Envelope()
