# covers: V1-A07, V1-A08
"""Pure template validation (W1-D02): one test per error class, plus the truth cases."""

import io
from datetime import date
from typing import Any, BinaryIO

import pytest

from app.schemas.v1_envelope import Envelope
from app.schemas.v1_imports import ImportSettings, RowError
from app.services.imports.validate import validate_files

LOCATIONS = (
    "location_id,name,type,street,city,state,zip\n"
    "H1,North Hub,hub,301 S Monroe St,Tallahassee,FL,32301\n"
    "P1,Pantry One,pantry,201 E University Ave,Gainesville,FL,32601\n"
)
PRODUCTS = "product_id,name,unit\nRICE,Rice,case\nBEANS,Beans,case\n"
INVENTORY = (
    "location_id,product_id,batch_id,quantity,expiry_date,non_expiring\n"
    "H1,RICE,B1,40,2026-12-01,\n"
    "P1,BEANS,B2,5,,true\n"
)
DEMAND = (
    "location_id,product_id,date,quantity,basis\n"
    "P1,RICE,2026-11-01,3,demand\n"
    "P1,RICE,2026-11-02,,demand\n"
)
PANTRY = ImportSettings(mode="PANTRY", timezone="America/New_York", as_of_date=date(2026, 11, 4))


def _files(**overrides: str | bytes) -> dict[Any, BinaryIO]:
    texts = {"locations": LOCATIONS, "products": PRODUCTS, "inventory": INVENTORY,
             "demand_history": DEMAND, **overrides}
    return {name: io.BytesIO(t if isinstance(t, bytes) else t.encode("utf-8"))
            for name, t in texts.items() if t is not None}


def _only_error(**overrides: str | bytes) -> RowError:
    report = validate_files(_files(**overrides), PANTRY)
    assert not report.ok
    assert report.error_count == 1, report.errors
    return report.errors[0]


def test_clean_files_are_ok():
    report = validate_files(_files(), PANTRY)
    assert report.ok, report.errors
    assert report.error_count == 0
    assert [loc.location_id for loc in report.rows.locations] == ["H1", "P1"]


# --- one test per error class -------------------------------------------------------------


def test_wrong_header_is_malformed():
    error = _only_error(products="product_id,name,units\nRICE,Rice,case\n")
    assert (error.file, error.line, error.code) == ("products", 1, "MALFORMED")
    assert error.column == "units"
    assert "unit" in error.reason


@pytest.mark.parametrize(
    ("name", "text", "column"),
    [
        ("locations", LOCATIONS + " P1 ,Again,pantry,1 Main St,Tampa,FL,33602\n", "location_id"),
        ("products", PRODUCTS + "RICE ,Rice again,case\n", "product_id"),
        ("inventory", INVENTORY + "H1, RICE ,B1 ,1,2026-12-02,\n", "batch_id"),
    ],
)
def test_duplicate_key(name, text, column):
    error = _only_error(**{name: text})
    assert (error.file, error.code, error.column) == (name, "DUPLICATE", column)
    assert error.line == text.count("\n")
    assert "line" in error.reason  # names the first occurrence


def test_negative_quantity():
    error = _only_error(inventory=INVENTORY + "H1,RICE,B3,-1,2026-12-01,\n")
    assert (error.file, error.line, error.column, error.code) == (
        "inventory", 4, "quantity", "NEGATIVE")
    assert error.value == "-1"


def test_fractional_quantity():
    error = _only_error(inventory=INVENTORY + "H1,RICE,B3,2.5,2026-12-01,\n")
    assert (error.line, error.column, error.code, error.value) == (
        4, "quantity", "FRACTIONAL", "2.5")


def test_unknown_location_id_in_inventory():
    error = _only_error(inventory=INVENTORY + "X9,RICE,B3,1,2026-12-01,\n")
    assert (error.file, error.line, error.column, error.code, error.value) == (
        "inventory", 4, "location_id", "UNKNOWN_ID", "X9")


def test_missing_expiry_without_non_expiring():
    error = _only_error(inventory=INVENTORY + "H1,RICE,B3,1,,\n")
    assert (error.line, error.code) == (4, "MISSING_EXPIRY")


def test_over_envelope_location():
    rows = "".join(f"P{i},Pantry {i},pantry,1 Main St,Tampa,FL,33602\n" for i in range(2, 101))
    report = validate_files(_files(locations=LOCATIONS + rows), PANTRY)
    assert report.error_count == 1
    error = report.errors[0]
    assert (error.file, error.line, error.code) == ("locations", 102, "OVER_ENVELOPE")
    assert "limit 100" in error.reason


def test_history_after_as_of_date_rejected():
    error = _only_error(demand_history=DEMAND + "P1,RICE,2026-11-05,1,demand\n")
    assert (error.file, error.line, error.column, error.code) == (
        "demand_history", 4, "date", "AFTER_AS_OF_DATE")


def test_history_on_the_as_of_date_accepted():
    """V1-SPEC §6.1 rejects history dated after as_of_date; the forecast keeps history up to and
    including its cutoff (= as_of_date), and planning starts the day after."""
    report = validate_files(_files(demand_history=DEMAND + "P1,RICE,2026-11-04,1,demand\n"),
                            PANTRY)
    assert report.ok, report.errors
    assert report.rows.demand_history[-1].day == date(2026, 11, 4)


def test_history_older_than_90_days_rejected():
    error = _only_error(demand_history=DEMAND + "P1,RICE,2026-08-05,1,demand\n")
    assert (error.line, error.column, error.code) == (4, "date", "OVER_ENVELOPE")
    assert "limit 90 days" in error.reason


def test_non_us_state_rejected():
    error = _only_error(
        locations=LOCATIONS + "P2,Toronto,pantry,100 Queen St W,Toronto,ON,M5H 2N2\n")
    assert (error.line, error.column, error.code) == (4, "state", "MALFORMED")
    assert "US" in error.reason


def test_non_iso_date_rejected():
    error = _only_error(demand_history=DEMAND + "P1,RICE,11/03/2026,1,demand\n")
    assert (error.line, error.column, error.code, error.value) == (
        4, "date", "MALFORMED", "11/03/2026")
    assert "use YYYY-MM-DD" in error.fix


def test_quantity_above_solver_bound_rejected():
    error = _only_error(inventory=INVENTORY + "H1,RICE,B3,250000,2026-12-01,\n")
    assert (error.line, error.column, error.code) == (4, "quantity", "OVER_ENVELOPE")
    assert "100000" in error.reason.replace(",", "")


def test_role_not_valid_for_mode():
    error = _only_error(locations=LOCATIONS + "S1,Store,store,1 Main St,Tampa,FL,33602\n")
    assert (error.line, error.column, error.code, error.value) == (4, "type", "MALFORMED", "store")
    assert "hub" in error.fix and "pantry" in error.fix


def test_error_cap_1000():
    bad = "".join(f"P1,RICE,B{i},-1,2026-12-01,\n" for i in range(5000))
    report = validate_files(_files(inventory=INVENTORY + bad), PANTRY)
    assert not report.ok
    assert report.error_count == 5000
    assert len(report.errors) == 1000
    assert report.errors[0].line == 4


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"products": "product_id,name\nRICE,Rice\n"}, "MALFORMED"),
        ({"products": PRODUCTS + "RICE,Again,case\n"}, "DUPLICATE"),
        ({"inventory": INVENTORY + "H1,RICE,B3,-1,2026-12-01,\n"}, "NEGATIVE"),
        ({"inventory": INVENTORY + "H1,RICE,B3,1.5,2026-12-01,\n"}, "FRACTIONAL"),
        ({"inventory": INVENTORY + "H1,NOPE,B3,1,2026-12-01,\n"}, "UNKNOWN_ID"),
        ({"inventory": INVENTORY + "H1,RICE,B3,1,,\n"}, "MISSING_EXPIRY"),
        ({"demand_history": DEMAND + "P1,RICE,2026-11-05,1,demand\n"}, "AFTER_AS_OF_DATE"),
        ({"inventory": INVENTORY + "H1,RICE,B3,100001,2026-12-01,\n"}, "OVER_ENVELOPE"),
    ],
)
def test_every_error_has_a_fix(overrides, code):
    error = _only_error(**overrides)
    assert error.code == code
    assert error.fix.strip() and error.fix != error.reason


def test_negative_history_fix_offers_blank_for_unknown():
    error = _only_error(demand_history=DEMAND + "P1,RICE,2026-11-03,-2,demand\n")
    assert error.code == "NEGATIVE"
    assert error.fix == (
        "Enter 0 or a positive whole number, or leave the cell blank if the value is unknown")


def test_rate_above_one_explains_fraction():
    error = _only_error(locations=LOCATIONS.replace(
        "location_id,name,type,street,city,state,zip\n",
        "location_id,name,type,street,city,state,zip,poverty_rate\n").replace(
        "32301\n", "32301,\n").replace("32601\n", "32601,12.5\n"))
    assert (error.line, error.column, error.code) == (3, "poverty_rate", "MALFORMED")
    assert "0.125 for 12.5%" in error.fix


# --- truth tests ----------------------------------------------------------------------------


def test_blank_demand_quantity_is_none():
    report = validate_files(_files(), PANTRY)
    assert [row.quantity for row in report.rows.demand_history] == [3, None]


def test_utf8_bom_and_crlf_accepted():
    files = _files(
        locations=b"\xef\xbb\xbf" + LOCATIONS.replace("\n", "\r\n").encode(),
        demand_history=DEMAND.replace("\n", "\r\n"),
    )
    report = validate_files(files, PANTRY)
    assert report.ok, report.errors
    assert report.rows.locations[0].location_id == "H1"
    assert report.rows.demand_history[1].quantity is None


def test_non_utf8_file_rejected_with_reason():
    latin1 = "product_id,name,unit\nRICE,Riz cr\xe8me,case\n".encode("latin-1")
    error = _only_error(products=latin1)
    assert (error.file, error.line, error.code) == ("products", 2, "MALFORMED")
    assert "UTF-8" in error.reason and "UTF-8" in error.fix


def test_huge_whole_number_is_over_envelope_not_a_crash():
    """Python refuses int() on more than 4,300 digits; the cell must still get a row error."""
    huge = "1" * 5000
    error = _only_error(inventory=INVENTORY.replace("H1,RICE,B1,40,", f"H1,RICE,B1,{huge},"))
    assert (error.file, error.line, error.column, error.code) == (
        "inventory", 2, "quantity", "OVER_ENVELOPE")
    assert "5,000-digit" in error.reason


def test_huge_decimal_is_rejected_before_it_overflows_its_column():
    products = ("product_id,name,unit,handling_units_per_unit\n"
                "RICE,Rice,case,1e30\nBEANS,Beans,case,\n")
    error = _only_error(products=products)
    assert (error.file, error.line, error.column, error.code) == (
        "products", 2, "handling_units_per_unit", "OVER_ENVELOPE")


def test_handling_units_that_round_to_zero_in_their_column_are_rejected():
    """Numeric(14, 6) stores 0.0000001 as 0, which breaks `handling_units_per_unit > 0`."""
    products = ("product_id,name,unit,handling_units_per_unit\n"
                "RICE,Rice,case,0.0000001\nBEANS,Beans,case,\n")
    error = _only_error(products=products)
    assert (error.file, error.line, error.column, error.code) == (
        "products", 2, "handling_units_per_unit", "MALFORMED")


def test_nul_character_rejected_before_the_bulk_load():
    error = _only_error(locations=LOCATIONS.replace("North Hub", "North\x00Hub"))
    assert (error.file, error.line, error.column, error.code) == ("locations", 2, "name",
                                                                  "MALFORMED")
    assert "NUL" in error.reason and error.fix


def test_nul_inside_a_number_is_reported_once():
    error = _only_error(inventory=INVENTORY.replace("H1,RICE,B1,40,", "H1,RICE,B1,4\x000,"))
    assert (error.line, error.column, error.code) == (2, "quantity", "MALFORMED")
    assert "NUL" in error.reason


@pytest.mark.parametrize("locations", [
    LOCATIONS.replace("location_id", "location_id\x00", 1),
    LOCATIONS.encode("utf-16-le"),  # saved as UTF-16 without a BOM: ASCII plus 0x00 is UTF-8
], ids=["stray-nul", "utf16-no-bom"])
def test_nul_in_the_header_is_one_readable_error(locations):
    """W2-06: the header must not reach the stored error with its NUL (PostgreSQL refuses it)."""
    error = _only_error(locations=locations)  # one error: the file is unusable, not re-checked
    assert (error.file, error.line, error.code) == ("locations", 1, "MALFORMED")
    for text in (error.column, error.reason, error.fix, error.value):
        assert "\x00" not in (text or "")
    assert "NUL" in error.reason and "CSV UTF-8" in error.fix


def test_ids_case_sensitive_after_trim():
    report = validate_files(_files(products=PRODUCTS + " rice ,Lowercase rice,case\n"), PANTRY)
    assert report.ok, report.errors
    assert [p.product_id for p in report.rows.products] == ["RICE", "BEANS", "rice"]
    error = _only_error(inventory=INVENTORY + "H1,rice,B3,1,2026-12-01,\n")
    assert (error.code, error.value) == ("UNKNOWN_ID", "rice")


def test_basis_sales_flagged():
    report = validate_files(_files(demand_history=DEMAND + "P1,BEANS,2026-11-01,2,sales\n"), PANTRY)
    assert report.ok, report.errors
    assert report.rows.sales_basis_series == {("P1", "BEANS")}
    assert report.rows.demand_history[-1].basis == "sales"


# --- rules the import depends on downstream ------------------------------------------------


def test_missing_required_file_reported():
    files = _files()
    del files["inventory"]
    report = validate_files(files, PANTRY)
    assert [(e.file, e.line, e.code) for e in report.errors] == [("inventory", 1, "MALFORMED")]


def test_as_of_defaults_to_day_after_last_history():
    report = validate_files(_files(), PANTRY.model_copy(update={"as_of_date": None}))
    assert report.ok, report.errors
    assert report.rows.as_of_date == date(2026, 11, 3)


def test_batches_parse_expiry_and_non_expiring():
    rows = validate_files(_files(), PANTRY).rows.batches
    assert [(b.batch_id, b.quantity, b.expiry_date, b.non_expiring) for b in rows] == [
        ("B1", 40, date(2026, 12, 1), False), ("B2", 5, None, True)]


def test_donations_summed_per_day_and_blank_kept_unknown():
    donations = ("location_id,product_id,date,quantity,donor\n"
                 "P1,RICE,2026-10-30,5,Church\nP1,RICE,2026-10-30,,Club\n"
                 "P1,RICE,2026-10-31,,Church\nP1,RICE,2026-10-31,5,Club\n"
                 "P1,RICE,2026-11-01,2,Church\nP1,RICE,2026-11-01,3,Club\n"
                 "P1,RICE,2026-11-02,0,\nP1,RICE,2026-11-03,,\n")
    report = validate_files(_files(donation_history=donations), PANTRY)
    assert report.ok, report.errors
    assert [(d.day, d.quantity) for d in report.rows.donation_history] == [
        (date(2026, 10, 30), None), (date(2026, 10, 31), None),  # one blank row: day unknown
        (date(2026, 11, 1), 5), (date(2026, 11, 2), 0), (date(2026, 11, 3), None)]


def test_inbound_outside_horizon_kept_and_marked():
    inbound = ("location_id,product_id,quantity,arrival_date,expiry_date,non_expiring\n"
               "P1,RICE,4,2026-11-06,2026-12-01,\nP1,RICE,6,2026-11-20,2026-12-01,\n")
    report = validate_files(_files(inbound=inbound), PANTRY)
    assert report.ok, report.errors
    assert [(r.line, r.within_horizon) for r in report.rows.inbound] == [(2, True), (3, False)]


def test_route_into_hub_rejected():
    routes = "from_location_id,to_location_id\nP1,H1\n"
    error = _only_error(routes=routes)
    assert (error.file, error.line, error.column, error.code) == (
        "routes", 2, "to_location_id", "MALFORMED")


def test_envelope_is_injectable():
    report = validate_files(_files(), PANTRY, Envelope(max_locations=1))
    assert [(e.code, e.line) for e in report.errors] == [("OVER_ENVELOPE", 3)]
