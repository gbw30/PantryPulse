# covers: V1-A14, V1-A15
"""Deterministic baselines with declared tie-breaks (W1-S02).

Declared order: earliest first-deficit day, then location_id, then product_id. Sources for a
receiver: SOONEST_EXPIRY_FIRST takes senders by their earliest eligible expiry (non-expiring
last), then travel days, then location_id. Each request takes the largest quantity the
per-product feasibility probe accepts; the union is re-verified before publication.
"""

from datetime import date

import pytest

from app.schemas.v1_planning import CapacityV3, ReserveV3
from app.services.optimization.methods import run_method
from app.services.optimization.verify import verify_plan
from tests.optimization.test_retail_oracle import FIXTURES, load


def scenario(name, **changes):
    s, _ = load(name)
    return s.model_copy(update=changes)


def moved(result):
    return sorted(
        (t.product_id, t.from_location_id, t.to_location_id, t.quantity, t.batch_ids)
        for t in result.transfers
    )


def two_senders():
    """S1 holds 5 non-expiring units; S2 holds 3 expiring 11-05; B sells 1/day, no stock.

    Both routes take 1 day (arrival 11-03); B receives at most 3 handling units per day.
    Soonest-expiry-first serves B's 7 lost sales from S2 first even though S1 sorts first by
    id: S2 -> B 3 units (they sell 11-03..11-05, before expiry), which fills B's receiving
    capacity, so S1 sends nothing.
    """
    s, _ = load("retail-day5-expiry")
    stores = tuple(
        s.locations[0].model_copy(update={"id": i, "name": f"Store {i}"}) for i in ("S1", "S2")
    )
    batches = (
        s.batches[0].model_copy(
            update={
                "id": "s1b",
                "location_id": "S1",
                "quantity": 5,
                "expiry_date": None,
                "non_expiring": True,
            }
        ),
        s.batches[0].model_copy(
            update={
                "id": "s2b",
                "location_id": "S2",
                "quantity": 3,
                "expiry_date": date(2026, 11, 5),
            }
        ),
    )
    demand = (
        s.demand[0].model_copy(update={"location_id": "S1"}),
        s.demand[0].model_copy(update={"location_id": "S2"}),
        s.demand[1],
    )
    routes = tuple(
        s.routes[0].model_copy(update={"from_location_id": i, "travel_days": 1})
        for i in ("S1", "S2")
    )
    receiving = CapacityV3(location_id="B", receiving=3, dispatch=None, storage=None)
    return s.model_copy(
        update={
            "locations": (*stores, s.locations[1]),
            "batches": batches,
            "demand": demand,
            "routes": routes,
            "capacities": (receiving,),
        }
    )


def test_no_transfers_is_empty_and_verified():
    for name in FIXTURES:
        result = run_method(scenario(name), "NO_TRANSFERS", "UNITS")
        assert (result.verified, result.transfers, result.native_status) == (True, (), None)
        assert all(
            (e.unmet_with_plan, e.expired_with_plan)
            == (e.unmet_without_plan, e.expired_without_plan)
            for e in result.effects
        )


def test_soonest_expiry_first_moves_earliest_batches():
    result = run_method(two_senders(), "SOONEST_EXPIRY_FIRST", "UNITS")
    assert moved(result) == [("P", "S2", "B", 3, ("s2b",))]


def test_baselines_deterministic():
    runs = {
        result.model_dump_json()
        for result in (
            run_method(two_senders(), "SOONEST_EXPIRY_FIRST", "UNITS") for _ in range(10)
        )
    }
    assert len(runs) == 1


def test_fefo_respected():
    """lost-vs-waste: B loses days 6-7 (2 units); A's shipment of 2 draws a1 (11-03) first."""
    result = run_method(scenario("retail-lost-vs-waste"), "SOONEST_EXPIRY_FIRST", "UNITS")
    assert moved(result) == [("P", "A", "B", 2, ("a1", "a2"))]


def test_hubs_never_receive():
    s = scenario("retail-usd-no-flip")
    back = s.routes[0].model_copy(update={"from_location_id": "B", "to_location_id": "D"})
    s = s.model_copy(update={"routes": (*s.routes, back)})
    for method in ("SOONEST_EXPIRY_FIRST", "RETAIL_OPTIMIZED"):
        result = run_method(s, method, "UNITS")
        assert result.verified and all(t.to_location_id != "D" for t in result.transfers)
    plan = run_method(s, "SOONEST_EXPIRY_FIRST", "UNITS").transfers
    into_dc = plan[0].model_copy(
        update={
            "product_id": "Q",
            "from_location_id": "B",
            "to_location_id": "D",
            "batch_ids": ("q1",),
        }
    )
    assert "ROUTE_NOT_ALLOWED" in verify_plan(s, (into_dc,)).violations


@pytest.mark.parametrize(("floor", "sent", "excess"), [(0, 2, 5), (3, 1, 2)])
def test_retail_store_sends_only_surplus_beyond_protected_7_day_forecast_plus_reserve(
    floor, sent, excess
):
    """lost-vs-waste: A holds 11 units and sells 1/day, so it ends day 7 with 4 - y units.

    B wants its 2 lost sales. With no reserve A gives both; sending 5 would leave A 6 units for
    its own 7-day forecast. With a reserve of 3, 4 - y >= 3 allows only y = 1; 2 breaks it.
    """
    s = scenario(
        "retail-lost-vs-waste",
        reserves=(ReserveV3(location_id="A", product_id="P", floor=floor),),
    )
    result = run_method(s, "SOONEST_EXPIRY_FIRST", "UNITS")
    assert [t.quantity for t in result.transfers] == [sent]
    too_many = result.transfers[0].model_copy(
        update={"quantity": excess, "batch_ids": ("a1", "a2")}
    )
    assert "DONOR_PROTECTION" in verify_plan(s, (too_many,)).violations


@pytest.mark.parametrize("measure", ("UNITS", "USD"))
@pytest.mark.parametrize("name", FIXTURES)
def test_every_baseline_result_passes_independent_verifier(name, measure):
    s = scenario(name)
    for method in ("NO_TRANSFERS", "SOONEST_EXPIRY_FIRST"):
        result = run_method(s, method, measure)
        assert result.verified, (method, result.failure_reason)
        assert verify_plan(s, result.transfers).passed
