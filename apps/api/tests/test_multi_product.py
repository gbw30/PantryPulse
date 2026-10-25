"""More than two products (user decision 2026-10-25): caps and the product-create contract."""

import pytest
from pydantic import ValidationError

from app.main import app
from app.repositories import planning
from app.repositories.operations_api import MAX_ACTIVE_PRODUCTS
from app.schemas.operations_api import ProductCreate
from app.schemas.optimization_api import AssumptionsPayload
from app.schemas.or_inputs import ORInputPackage


def max_len(field):
    return next(m.max_length for m in field.metadata if hasattr(m, "max_length"))


def test_planning_and_solver_accept_up_to_eight_products():
    assert planning.MAX_PLANNING_PRODUCTS == 8
    assert max_len(ORInputPackage.model_fields["products"]) == planning.MAX_PLANNING_PRODUCTS
    assert MAX_ACTIVE_PRODUCTS == planning.MAX_PLANNING_PRODUCTS


def test_assumption_lists_scale_with_the_product_cap():
    fields = AssumptionsPayload.model_fields
    assert max_len(fields["handling"]) == planning.MAX_PLANNING_PRODUCTS
    assert max_len(fields["reserves"]) == 14 * planning.MAX_PLANNING_PRODUCTS


def test_product_create_requires_a_name_and_a_base_unit():
    assert ProductCreate(name="Canned vegetables", base_unit="can").category_name is None
    for bad in ({"name": " ", "base_unit": "can"}, {"name": "Rice", "base_unit": ""}):
        with pytest.raises(ValidationError):
            ProductCreate(**bad)
    with pytest.raises(ValidationError):
        ProductCreate(name="Rice", base_unit="kg", unexpected=True)


def test_product_create_route_is_a_presenter_write():
    operation = app.openapi()["paths"]["/api/v1/products"]["post"]
    body = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    assert body.endswith("/ProductCreate")
    headers = {p["name"].lower() for p in operation["parameters"] if p["in"] == "header"}
    assert {"idempotency-key", "x-csrf-token"} <= headers
