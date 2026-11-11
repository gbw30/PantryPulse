# covers: V1-A13, V1-A23
"""W3-F05: danger ranking and the site inspector's projection (V1-SPEC §6.6, W2-06 §3).

Two networks go through the real import and the production forecast.v1 job, as of 2026-11-04
(planning days Nov 5–11). Every demand history is 21 constant days, so seasonal naive repeats
it and the targets are known without running the forecast in the test.

Pantry network (RICE in cases, MILK in lb; all stock non-expiring unless noted):

| location | demand / day | supply | what it pins |
|---|---|---|---|
| PA | RICE 10, MILK 4 | RICE 35, MILK 7 | worst product by share, not by units |
| PB | RICE 10 | RICE 21; donations 3/day | donations never count as supply |
| PC | RICE 10 | inbound 14 on Nov 5 | inbound enters once |
| PD | RICE 10 | inbound 50 on Nov 12 (outside) | outside-horizon inbound is not counted |
| PE | RICE 10, only 10 days | RICE 5 expiring Nov 7 | unknown demand: no row, unknown cells |

Retail network (MILK in cases, BREAD in loaves):

| location | demand / day | stock | what it pins |
|---|---|---|---|
| D1 (DC) | none | MILK 50 expiring Nov 8 | expiry share at a sender |
| S1 | MILK 2, BREAD 1 | MILK 20 expiring Nov 7, BREAD 7 | expiry share beats unmet share |
| S2 | MILK 2 | MILK 4 | unmet share |
"""

import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.repositories.forecast_history import HistoryRejected
from app.schemas.v1_imports import NewNetwork
from app.schemas.v1_networks import DangerRow, ProductProjection
from app.services.danger.ranking import (
    HIGH,
    MEDIUM,
    Line,
    band,
    danger_ranking,
    get_danger,
    get_projection,
)
from tests.forecasting.test_network_forecast import (
    HORIZON,
    SESSION,
    back,
    forecast_stack,
    import_network,
    run,
)

SCHEMA = "w3_danger_test"
DAYS = tuple(HORIZON)
UNKNOWN = (None,) * 7


def history(rows: list[tuple[str, str, int]], basis: str = "demand", days: int = 21) -> str:
    return "location_id,product_id,date,quantity,basis\n" + "".join(
        f"{loc},{prod},{d},{qty},{basis}\n" for loc, prod, qty in rows for d in back(days))


PANTRY = {
    "locations": (
        "location_id,name,type,street,city,state,zip,latitude,longitude,"
        "receiving_capacity_per_day,poverty_rate,snap_rate\n"
        "H1,North Hub,hub,301 S Monroe St,Tallahassee,FL,32301,30.4383,-84.2807,,,\n"
        + "".join(f"P{x},Pantry {x},pantry,{i} Main St,Gainesville,FL,32601,29.65{i},-82.32{i},"
                  ",0.21,0.18\n" for i, x in enumerate("ABCDE"))),
    "products": "product_id,name,unit,unit_value_usd,handling_units_per_unit\n"
                "RICE,Rice,case,,1\nMILK,Milk,lb,,1\n",
    "inventory": "location_id,product_id,batch_id,quantity,expiry_date,non_expiring,received_date\n"
                 "H1,RICE,B1,100,2026-11-30,,\nPA,RICE,B1,35,,true,\nPA,MILK,B1,7,,true,\n"
                 "PB,RICE,B1,21,,true,\nPE,RICE,B1,5,2026-11-07,,\n",
    "demand_history": history([("PA", "RICE", 10), ("PA", "MILK", 4), ("PB", "RICE", 10),
                               ("PC", "RICE", 10), ("PD", "RICE", 10)])
                      + history([("PE", "RICE", 10)], days=10).split("\n", 1)[1],
    "donation_history": "location_id,product_id,date,quantity,donor\n" + "".join(
        f"PB,RICE,{d},3,Grocer\n" for d in back(21)),
    "inbound": "location_id,product_id,quantity,arrival_date,expiry_date,non_expiring,source,"
               "reference\nPC,RICE,14,2026-11-05,,true,,\nPD,RICE,50,2026-11-12,,true,,\n",
}

RETAIL = {
    "locations": (
        "location_id,name,type,street,city,state,zip,latitude,longitude,"
        "receiving_capacity_per_day,poverty_rate,snap_rate\n"
        "D1,Central DC,distribution_center,1 Dock Rd,Orlando,FL,32801,28.5383,-81.3792,,,\n"
        "S1,Store One,store,2 Main St,Orlando,FL,32801,28.5401,-81.3801,,,\n"
        "S2,Store Two,store,3 Main St,Orlando,FL,32801,28.5422,-81.3822,,,\n"),
    "products": "product_id,name,unit,unit_value_usd,handling_units_per_unit\n"
                "MILK,Milk,case,3.00,1\nBREAD,Bread,loaf,2.50,1\n",
    "inventory": "location_id,product_id,batch_id,quantity,expiry_date,non_expiring,received_date\n"
                 "D1,MILK,B1,50,2026-11-08,,\nS1,MILK,B1,20,2026-11-07,,\n"
                 "S1,BREAD,B1,7,,true,\nS2,MILK,B1,4,,true,\n",
    "demand_history": history([("S1", "MILK", 2), ("S1", "BREAD", 1), ("S2", "MILK", 2)],
                              basis="sales"),
}


def expected(daily: int, supply: int) -> tuple[Decimal, int, date | None]:
    """Constant demand, non-expiring supply usable from day 1: (share, unmet, first deficit)."""
    unmet = max(0, 7 * daily - supply)
    return Decimal(unmet) / (7 * daily), unmet, DAYS[supply // daily] if unmet else None


def line(location: str, product: str, target, unmet, expired=None, stock=0, inbound=0,
         unit="case") -> Line:
    served = tuple(t - u for t, u in zip(target, unmet, strict=True))
    return Line(location, ProductProjection(
        product_id=product, unit=unit, dates=DAYS, target=target, served=served, unmet=unmet,
        eligible_stock_now=stock, expiring_unsold=expired, donation_forecast=None), inbound)


def summary(rows) -> list[tuple]:
    return [(r.location_id, r.score_ratio, r.reason, r.driving_product_id, r.driving_units,
             r.unit, r.first_deficit_date) for r in rows]


# --- the ranking rule, on hand-built projections -----------------------------------------------

def test_band_thresholds_are_declared():
    assert (HIGH, MEDIUM) == (Decimal("0.50"), Decimal("0.20"))
    assert [band(Decimal(x)) for x in ("1", "0.5", "0.4999", "0.2", "0.1999", "0")] == [
        "high", "high", "medium", "medium", "low", "low"]


def test_ties_broken_by_earliest_first_deficit_day():
    flat = (2,) * 7  # 14 over the week; 7 unmet is a share of 0.5 wherever it falls
    late, early = (0, 0, 0, 1, 2, 2, 2), (0, 1, 1, 1, 1, 1, 2)
    rows = danger_ranking([
        line("A", "X", flat, late),
        line("C", "X", flat, early),
        line("B", "X", flat, early),
        line("D", "X", flat, late), line("D", "Y", flat, early),  # Y drives D: earlier deficit
    ], "PANTRY")
    assert [(r.location_id, r.rank, r.driving_product_id, r.first_deficit_date)
            for r in rows] == [
        ("B", 1, "X", DAYS[1]), ("C", 2, "X", DAYS[1]), ("D", 3, "Y", DAYS[1]),
        ("A", 4, "X", DAYS[3])]
    assert {r.score_ratio for r in rows} == {Decimal("0.5")}


def test_unmet_wins_a_retail_tie_and_pantry_ignores_expiry():
    both = line("A", "X", (2,) * 7, (0, 0, 0, 1, 2, 2, 2), expired=(0, 0, 0, 7, 0, 0, 0),
                stock=14)  # 7/14 unmet and 7/14 expiring, both first on day 4
    assert summary(danger_ranking([both], "RETAIL")) == [
        ("A", Decimal("0.5"), "unmet", "X", 7, "case", DAYS[3])]
    expiry = line("A", "X", (2,) * 7, (0, 0, 0, 0, 0, 0, 1), expired=(0, 9, 0, 0, 0, 0, 0),
                  stock=10)
    assert summary(danger_ranking([expiry], "PANTRY")) == [
        ("A", Decimal("0.0714"), "unmet", "X", 1, "case", DAYS[6])]


def test_expiry_share_counts_confirmed_inbound_in_its_stock():
    """Verifier F4: 5 of 10 on hand + 10 arriving expire unsold, a share of 0.25, not 0.5."""
    arriving = line("A", "X", (0,) * 7, (0,) * 7, expired=(0, 0, 0, 5, 0, 0, 0), stock=10,
                    inbound=10)
    assert summary(danger_ranking([arriving], "RETAIL")) == [
        ("A", Decimal("0.25"), "expiry", "X", 5, "case", DAYS[3])]


def test_unmet_wins_a_retail_tie_between_locations():
    expiry = line("A", "X", (2,) * 7, (0,) * 7, expired=(0, 0, 0, 7, 0, 0, 0), stock=14)
    unmet = line("B", "X", (2,) * 7, (0, 0, 0, 1, 2, 2, 2))  # 0.5 from day 4, as A's expiry
    assert summary(danger_ranking([expiry, unmet], "RETAIL")) == [
        ("B", Decimal("0.5"), "unmet", "X", 7, "case", DAYS[3]),
        ("A", Decimal("0.5"), "expiry", "X", 7, "case", DAYS[3])]


# --- the services, on imported networks with real forecast runs --------------------------------

@pytest.fixture(scope="module")
def nets(tmp_path_factory):
    with forecast_stack(SCHEMA, tmp_path_factory.mktemp("imports")) as stack:
        made = {}
        for mode, files in (("PANTRY", PANTRY), ("RETAIL", RETAIL)):
            network = import_network(stack, files, NewNetwork(
                name=f"Danger {mode} {uuid.uuid4().hex[:6]}", mode=mode,
                timezone="America/New_York"))
            made[mode] = SimpleNamespace(id=network.network_id, run=run(stack, network))
        yield SimpleNamespace(stack=stack, **made)


def danger(nets, mode):
    net = getattr(nets, mode)
    return get_danger(nets.stack, SESSION, net.id, net.run)


def projection(nets, mode, location):
    net = getattr(nets, mode)
    products = get_projection(nets.stack, SESSION, net.id, net.run, location).products
    return {p.product_id: p for p in products}


@pytest.mark.integration
def test_pantry_score_is_worst_product_unmet_share_of_7_day_demand(nets):
    rice, milk = expected(10, 35), expected(4, 7)
    assert milk[0] > rice[0] and milk[1] < rice[1]  # the share decides, not the units
    want = sorted([
        ("PA", *max(((*rice, "RICE", "case")), ((*milk, "MILK", "lb")))),
        ("PB", *expected(10, 21), "RICE", "case"),
        ("PC", *expected(10, 14), "RICE", "case"),
        ("PD", *expected(10, 0), "RICE", "case"),
    ], key=lambda w: -w[1])
    ranking = danger(nets, "PANTRY")
    assert (ranking.network_id, ranking.forecast_run_id, ranking.mode) == (
        nets.PANTRY.id, nets.PANTRY.run, "PANTRY")
    assert [(r.rank, r.location_id, r.score_ratio, r.reason, r.driving_product_id,
             r.driving_units, r.unit, r.first_deficit_date, r.band) for r in ranking.rows] == [
        (i, loc, share, "unmet", prod, units, unit, first, band(share))
        for i, (loc, share, units, first, prod, unit) in enumerate(want, 1)]


@pytest.mark.integration
def test_unknown_demand_is_not_scored_and_projection_shows_unknown(nets):
    assert "PE" not in {r.location_id for r in danger(nets, "PANTRY").rows}
    rice = projection(nets, "PANTRY", "PE")["RICE"]
    assert (rice.target, rice.served, rice.unmet, rice.expiring_unsold) == (UNKNOWN,) * 4
    assert (rice.eligible_stock_now, rice.donation_forecast, rice.dates) == (5, None, DAYS)


@pytest.mark.integration
def test_never_sums_units_across_products(nets):
    assert set(DangerRow.model_fields) == {  # no cross-product total in the contract
        "location_id", "rank", "score_ratio", "band", "reason", "driving_product_id",
        "driving_units", "unit", "first_deficit_date", "basis"}  # basis: a label (W5-L01)
    for mode in ("PANTRY", "RETAIL"):
        for row in danger(nets, mode).rows:
            own = projection(nets, mode, row.location_id)
            driving = own[row.driving_product_id]
            lost = driving.unmet if row.reason == "unmet" else driving.expiring_unsold
            assert (row.driving_units, row.unit) == (sum(lost), driving.unit)
    pa = projection(nets, "PANTRY", "PA")
    assert (sum(pa["RICE"].unmet), sum(pa["MILK"].unmet)) == (35, 21)
    assert next(r for r in danger(nets, "PANTRY").rows if r.location_id == "PA").driving_units \
        == 21


@pytest.mark.integration
def test_donation_forecasts_do_not_change_score(nets):
    rice = projection(nets, "PANTRY", "PB")["RICE"]
    assert rice.donation_forecast == (3,) * 7  # shown, labeled "not confirmed" by the web
    assert rice.served == (10, 10, 1, 0, 0, 0, 0)
    pb = next(r for r in danger(nets, "PANTRY").rows if r.location_id == "PB")
    assert pb.score_ratio == expected(10, 21)[0] != expected(10, 21 + 21)[0]


@pytest.mark.integration
def test_inbound_changes_score_once(nets):
    rows = {r.location_id: r for r in danger(nets, "PANTRY").rows}
    assert rows["PC"].score_ratio == expected(10, 14)[0] == Decimal("0.8")
    assert expected(10, 0)[0] != rows["PC"].score_ratio != expected(10, 28)[0]
    assert rows["PD"].score_ratio == 1  # its delivery arrives Nov 12, after the horizon
    pc = projection(nets, "PANTRY", "PC")["RICE"]
    assert (pc.eligible_stock_now, pc.served) == (0, (10, 4, 0, 0, 0, 0, 0))


@pytest.mark.integration
def test_retail_score_is_max_of_unmet_share_and_expiry_share_with_reason(nets):
    s1 = projection(nets, "RETAIL", "S1")
    assert s1["MILK"].expiring_unsold == (0, 0, 14, 0, 0, 0, 0)
    assert s1["MILK"].unmet == (0, 0, 0, 2, 2, 2, 2)  # 8/14 = 0.5714 < 14/20 = 0.7
    assert s1["BREAD"].expiring_unsold is None  # non-expiring only: no expiry data
    assert summary(danger(nets, "RETAIL").rows) == [
        ("D1", Decimal(1), "expiry", "MILK", 50, "case", date(2026, 11, 8)),
        ("S2", Decimal("0.7143"), "unmet", "MILK", 10, "case", date(2026, 11, 7)),
        ("S1", Decimal("0.7"), "expiry", "MILK", 14, "case", date(2026, 11, 7)),
    ]


@pytest.mark.integration
def test_get_danger_endpoint_matches_service(nets):
    from fastapi.testclient import TestClient

    from app.main import create_app
    from app.routers.forecasts import presenter, runtime

    app = create_app()
    app.dependency_overrides[runtime] = lambda: nets.stack
    app.dependency_overrides[presenter] = lambda: SESSION
    client, net = TestClient(app), nets.PANTRY
    base = f"/api/v1/networks/{net.id}"
    response = client.get(f"{base}/danger", params={"forecast_run_id": str(net.run)})
    assert response.status_code == 200, response.text
    assert response.json() == danger(nets, "PANTRY").model_dump(mode="json")
    response = client.get(f"{base}/projection",
                          params={"forecast_run_id": str(net.run), "location_id": "PA"})
    assert response.status_code == 200, response.text
    assert response.json() == get_projection(
        nets.stack, SESSION, net.id, net.run, "PA").model_dump(mode="json")
    for url, params, code in (
        (f"/api/v1/networks/{uuid.uuid4()}/danger", {"forecast_run_id": str(net.run)},
         "NETWORK_NOT_FOUND"),
        (f"{base}/danger", {"forecast_run_id": str(nets.RETAIL.run)}, "FORECAST_RUN_NOT_FOUND"),
        (f"{base}/projection", {"forecast_run_id": str(net.run), "location_id": "NOPE"},
         "LOCATION_NOT_FOUND"),
    ):
        response = client.get(url, params=params)
        assert (response.status_code, code) == (404, code) and code in response.text
    with pytest.raises(HistoryRejected):
        get_danger(nets.stack, SESSION, net.id, uuid.uuid4())
