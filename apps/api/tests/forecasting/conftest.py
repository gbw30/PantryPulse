from datetime import UTC, date, datetime, timedelta
from uuid import UUID, uuid5

import pytest

from app.services.forecasting.schemas import ForecastPolicy, HistoryBundle, SeriesKey, SeriesScope

ORG = UUID(int=1)
DATASET = UUID(int=2)
SITE = UUID(int=3)
PRODUCT = UUID(int=4)
CUTOFF = date(2026, 10, 23)
AS_OF = datetime(2026, 10, 24, tzinfo=UTC)
KEY = SeriesKey(organization_id=ORG, site_id=SITE, product_id=PRODUCT, target_type="DEMAND")


def ref(name, revision=1, recorded_at="2026-01-01T00:00:00Z"):
    return {
        "organization_id": str(ORG),
        "dataset_id": str(DATASET),
        "logical_key": name,
        "revision_id": str(uuid5(DATASET, f"{name}:{revision}")),
        "revision": revision,
        "recorded_at": recorded_at,
    }


def demand(day, requested=10, fulfilled=8, unmet=2, **kwargs):
    return {
        "source": ref(f"demand:{day}"),
        "key": KEY.model_dump(mode="json"),
        "day": str(day),
        "requested_units": requested,
        "fulfilled_units": fulfilled,
        "unmet_units": unmet,
        "source_classification": "SIMULATED",
        **kwargs,
    }


@pytest.fixture
def policy():
    return ForecastPolicy(
        policy_version="experimental-v1",
        sparse_window_days=14,
        sparse_min_samples=3,
    )


@pytest.fixture
def history():
    def build(rows=None, **kwargs):
        return HistoryBundle(
            organization_id=ORG,
            dataset_id=DATASET,
            scope=(SeriesScope(key=KEY, unit="meal", timezone="America/New_York"),),
            demand=tuple(
                rows
                if rows is not None
                else [demand(CUTOFF - timedelta(days=i), 10 + i, 8 + i, 2) for i in range(21)]
            ),
            **kwargs,
        )

    return build
