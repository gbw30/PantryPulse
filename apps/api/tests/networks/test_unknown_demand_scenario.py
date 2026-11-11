# covers: V1-A23
"""W4-03 on the deployed path: import → forecast.v1 → create_scenario → method.

PX's demand history is 20 blank days, so forecast.v1 lists it INSUFFICIENT_DATA (NO_HISTORY)
and the frozen scenario gives it no demand row (never zero). PX must ship none of its 6 cases,
and the scenario's assumptions must say so. (EGP_PI_INSPIRED passes before the fix too: PY is
its only positive-target pantry, so the product is a singleton and is not solved.)
"""

import uuid
from types import SimpleNamespace

import pytest

from app.schemas.v1_imports import NewNetwork
from app.schemas.v1_planning import ScenarioOptions
from app.services.networks.api import create_scenario
from app.services.optimization.methods import run_method
from tests.forecasting.test_network_forecast import (
    SESSION,
    back,
    forecast_stack,
    import_network,
    run,
)

pytestmark = pytest.mark.integration
SCHEMA = "w4_unknown_demand_test"

FILES = {
    "locations": (
        "location_id,name,type,street,city,state,zip,latitude,longitude,"
        "receiving_capacity_per_day,poverty_rate,snap_rate\n"
        "H1,Hub,hub,1 A St,Gainesville,FL,32601,29.65,-82.32,,,\n"
        "PX,Pantry X,pantry,2 A St,Gainesville,FL,32601,29.651,-82.321,,0.2,0.2\n"
        "PY,Pantry Y,pantry,3 A St,Gainesville,FL,32601,29.652,-82.322,,0.3,0.3\n"),
    "products": "product_id,name,unit,unit_value_usd,handling_units_per_unit\nRICE,Rice,case,,1\n",
    "inventory": "location_id,product_id,batch_id,quantity,expiry_date,non_expiring,received_date\n"
                 "PX,RICE,B1,6,,true,\n",
    "demand_history": "location_id,product_id,date,quantity,basis\n"
                      + "".join(f"PX,RICE,{d},,demand\n" for d in back(20))
                      + "".join(f"PY,RICE,{d},10,demand\n" for d in back(21)),
    "routes": "from_location_id,to_location_id,travel_days,cost_per_handling_unit,"
              "capacity_per_batch,disabled\nPX,PY,1,,,\nH1,PY,1,,,\nH1,PX,1,,,\n",
}


@pytest.fixture(scope="module")
def frozen(tmp_path_factory):
    with forecast_stack(SCHEMA, tmp_path_factory.mktemp("imports")) as stack:
        network = import_network(stack, FILES, NewNetwork(
            name=f"Unknown {uuid.uuid4().hex[:6]}", mode="PANTRY", timezone="America/New_York"))
        yield SimpleNamespace(payload=create_scenario(stack, SESSION, network.network_id,
                                                      ScenarioOptions(
            dataset_version_id=network.dataset_version_id, forecast_run_id=run(stack, network),
            transfer_mode="HUB_AND_PANTRY", planning_days=3)).payload)


def test_scenario_says_the_unknown_demand_pantry_sends_none(frozen):
    p = frozen.payload
    assert "PX" not in {d.location_id for d in p.demand}
    line = next(a for a in p.assumptions if "no demand target (not zero)" in a)
    assert "PX × RICE (INSUFFICIENT_DATA)" in line
    assert "sends none of that product" in line


@pytest.mark.parametrize("method", ["EQUAL_SHARE", "MOST_URGENT_FIRST", "CLASSICAL_GP",
                                    "EGP_PI_INSPIRED"])
def test_unknown_demand_pantry_ships_nothing(frozen, method):
    result = run_method(frozen.payload, method, "UNITS")
    assert result.verified, result.failure_reason
    assert sum(t.quantity for t in result.transfers if t.from_location_id == "PX") == 0
