"""Typed public contracts for the dashboard summary and shortage reads (PP-51).

The routes' JSON must not change: these models only describe and validate it.
"""

from datetime import UTC, date, datetime
from uuid import uuid4

from app.main import app
from app.schemas.dashboard_api import DashboardSummary, ShortageProjection
from app.schemas.inventory_api import InventorySnapshot


def response_ref(path):
    schema = app.openapi()["paths"][path]["get"]["responses"]["200"]["content"]["application/json"][
        "schema"
    ]
    return schema.get("$ref", "").rsplit("/", 1)[-1]


def test_dashboard_and_shortage_responses_are_typed_in_openapi():
    assert response_ref("/api/v1/dashboard/summary") == "DashboardSummary"
    assert response_ref("/api/v1/shortages/{forecast_run_id}") == "ShortageProjection"


def snapshot():
    now = datetime(2026, 10, 25, 12, 30, 5, 123456, tzinfo=UTC)
    return InventorySnapshot(
        site_id=uuid4(),
        site_name="Riverbend Pantry",
        product_id=uuid4(),
        product_name="Shelf-stable meals",
        base_unit="meal",
        timezone="America/New_York",
        local_date=date(2026, 10, 25),
        observed_at=now,
        inventory_version=3,
        on_hand_quantity=40,
        usable_quantity=40,
        excluded_quantity=0,
        excluded_quantities={},
        lots=(),
    )


def test_dashboard_summary_serializes_exactly_like_the_untyped_route():
    now = datetime(2026, 10, 25, 12, 30, 5, 123456, tzinfo=UTC)
    run = {
        "id": str(uuid4()),
        "job_id": str(uuid4()),
        "planning_ready": True,
        "recorded_at": now.isoformat(),
    }
    item = snapshot()
    legacy = {
        "observed_at": now.isoformat(),
        "inventory": [item.model_dump(mode="json")],
        "latest_forecast": run,
    }
    typed = DashboardSummary(observed_at=now, inventory=(item,), latest_forecast=run)
    assert typed.model_dump(mode="json") == legacy
    empty = DashboardSummary(observed_at=now, inventory=(), latest_forecast=None)
    assert empty.model_dump(mode="json")["latest_forecast"] is None


def test_shortage_projection_serializes_exactly_like_the_untyped_route():
    now = datetime(2026, 10, 25, 12, 30, 5, 123456, tzinfo=UTC)
    legacy = {
        "forecast_run_id": str(uuid4()),
        "observed_at": now.isoformat(),
        "series": [
            {
                "site_id": str(uuid4()),
                "product_id": str(uuid4()),
                "base_unit": "meal",
                "actual_provider": "SEASONAL_NAIVE",
                "days": [
                    {
                        "day": "2026-10-26",
                        "demand": "70",
                        "served": "50",
                        "unmet": "20",
                        "eligible_end": "0",
                    },
                ],
            }
        ],
        "warnings": ["Physical stock only; confirmed supply lacks expiry declarations"],
    }
    typed = ShortageProjection.model_validate({**legacy, "observed_at": now})
    assert typed.model_dump(mode="json") == legacy


def test_shortage_day_quantities_must_be_nonnegative_integer_strings():
    bad = {"day": "2026-10-26", "demand": "-1", "served": "0", "unmet": "0", "eligible_end": "0"}
    payload = {
        "forecast_run_id": str(uuid4()),
        "observed_at": datetime(2026, 10, 25, tzinfo=UTC),
        "series": [
            {
                "site_id": str(uuid4()),
                "product_id": str(uuid4()),
                "base_unit": "meal",
                "actual_provider": "SEASONAL_NAIVE",
                "days": [bad],
            }
        ],
        "warnings": [],
    }
    try:
        ShortageProjection.model_validate(payload)
    except ValueError:
        return
    raise AssertionError("negative demand must be rejected")
