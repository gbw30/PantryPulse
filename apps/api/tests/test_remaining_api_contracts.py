from app.main import app


def test_operational_route_surface_is_present():
    paths = app.openapi()["paths"]
    for path in (
        "/api/v1/receipts", "/api/v1/receipts/{receipt_id}",
        "/api/v1/receipts/{receipt_id}/revisions", "/api/v1/receipts/{receipt_id}/post",
        "/api/v1/receipts/{receipt_id}/reconcile", "/api/v1/inventory/lots/{lot_id}/declarations",
        "/api/v1/supplies", "/api/v1/supplies/{supply_id}/confirmation",
        "/api/v1/imports/demand", "/api/v1/imports/donation-coverage",
        "/api/v1/dashboard/summary", "/api/v1/shortages/{forecast_run_id}",
        "/api/v1/planning-catalog", "/api/v1/planning-assumptions",
        "/api/v1/scenarios", "/api/v1/scenarios/{scenario_id}/plans",
        "/api/v1/scenarios/{scenario_id}/compare-methods", "/api/v1/plans/{record_id}",
        "/api/v1/plans/{plan_id}/review", "/api/v1/comparisons/{identity}",
    ):
        assert path in paths, path
