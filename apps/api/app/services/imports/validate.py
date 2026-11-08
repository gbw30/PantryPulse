"""Template row validation, pure and streaming (W1-D02).

One pass per file with the stdlib csv module. Cells are trimmed; IDs stay case-sensitive.
A row with any error is left out of the parsed result, and the report is ok only with zero
errors (all-or-nothing, V1-SPEC §6.1). An ID seen in a file counts as known for references
even when its row has another error, so one root cause is reported once, not per reference.
"""

import csv
import re
from array import array
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import BinaryIO

from app.schemas.v1_envelope import V1_ENVELOPE, Envelope
from app.schemas.v1_imports import ErrorCode, ImportSettings, RowError, ValidationReport
from app.schemas.v1_networks import REQUIRED_TEMPLATES, TemplateName
from app.schemas.v1_planning import ROLES_BY_MODE, ProductV3
from app.services.imports.columns import COLUMNS, header

# The or-input-v3 `Count` bound (or_inputs.py:14): a larger quantity would fail at scenario freeze.
MAX_QUANTITY = 100_000
MAX_DECIMAL = Decimal(99_999_999)  # the narrowest stored column, Numeric(14, 6), holds < 10^8
# The freeze's own limit (ProductV3, 1 to 1000), so the import refuses what the freeze would.
MAX_HANDLING_UNITS = next(m.le for m in ProductV3.model_fields["handling_units_per_unit"]
                          .metadata if hasattr(m, "le"))
HORIZON_DAYS = 7
ID_MAX_LENGTH = 64
US_STATES = frozenset(
    "AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH "
    "NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY".split()
)
INBOUND_SOURCES = ("dc_delivery", "supplier", "donation", "other")
FILE_ORDER: tuple[TemplateName, ...] = (
    "locations", "products", "inventory", "demand_history", "donation_history", "routes", "inbound"
)
HISTORY_FILES: tuple[TemplateName, ...] = ("demand_history", "donation_history")
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
DIGITS = re.compile(r"\d+")
DATE_FIX = "use YYYY-MM-DD, e.g. 2026-11-04"
BLANK_OK_QUANTITY_FIX = (
    "Enter 0 or a positive whole number, or leave the cell blank if the value is unknown"
)


@dataclass(frozen=True, slots=True)
class ParsedLocation:
    line: int
    location_id: str
    name: str
    role: str
    street: str
    city: str
    state: str
    zip: str
    latitude: Decimal | None
    longitude: Decimal | None
    receiving_capacity_per_day: Decimal | None  # None = no limit
    poverty_rate: Decimal | None  # manual override of the lookup
    snap_rate: Decimal | None


@dataclass(frozen=True, slots=True)
class ParsedProduct:
    line: int
    product_id: str
    name: str
    unit: str
    unit_value_usd: Decimal | None
    handling_units_per_unit: Decimal
    handling_units_given: bool  # False = the default 1, shown as an assumption


@dataclass(frozen=True, slots=True)
class ParsedBatch:
    line: int
    location_id: str
    product_id: str
    batch_id: str
    quantity: int
    expiry_date: date | None
    non_expiring: bool
    received_date: date | None


@dataclass(frozen=True, slots=True)
class HistoryRow:
    """One demand_history or donation_history row; quantity None = unknown, never zero."""

    line: int
    location_id: str
    product_id: str
    day: date
    quantity: int | None
    basis: str | None  # demand_history only
    donor: str | None  # donation_history only


@dataclass(frozen=True, slots=True)
class DonationDay:
    location_id: str
    product_id: str
    day: date
    quantity: int | None  # sum of the reported rows; None when any row was blank (unknown day)
    donor: str | None


@dataclass(frozen=True, slots=True)
class ParsedRoute:
    line: int
    from_location_id: str
    to_location_id: str
    travel_days: int | None
    cost_per_handling_unit: Decimal | None
    capacity_per_batch: Decimal | None
    disabled: bool


@dataclass(frozen=True, slots=True)
class ParsedInbound:
    line: int
    location_id: str
    product_id: str
    quantity: int
    arrival_date: date
    expiry_date: date | None
    non_expiring: bool
    source: str | None
    reference: str | None
    within_horizon: bool  # arrival in the seven days after as_of_date; others are listed


@dataclass(slots=True)
class ParsedNetwork:
    as_of_date: date
    files: frozenset[TemplateName]
    locations: list[ParsedLocation] = field(default_factory=list)
    products: list[ParsedProduct] = field(default_factory=list)
    batches: list[ParsedBatch] = field(default_factory=list)
    demand_history: list[HistoryRow] = field(default_factory=list)
    donation_history: list[DonationDay] = field(default_factory=list)
    routes: list[ParsedRoute] = field(default_factory=list)
    inbound: list[ParsedInbound] = field(default_factory=list)
    sales_basis_series: set[tuple[str, str]] = field(default_factory=set)


HistorySink = Callable[[TemplateName, HistoryRow], None]


class _Bad(Exception):
    """One cell error; raised by the cell parsers and caught per row."""

    def __init__(self, code: ErrorCode, reason: str, fix: str):
        self.code, self.reason, self.fix = code, reason, fix


def validate_files(
    files: Mapping[TemplateName, BinaryIO],
    settings: ImportSettings,
    envelope: Envelope = V1_ENVELOPE,
) -> ValidationReport:
    return Validator(settings, envelope).run(files)


class Validator:
    """Streaming validator. `history_sink` receives each clean history row instead of keeping
    it in memory (the import job COPYs them); without one, rows land in ParsedNetwork."""

    def __init__(
        self, settings: ImportSettings, envelope: Envelope = V1_ENVELOPE,
        history_sink: HistorySink | None = None,
    ):
        self.settings, self.envelope, self.history_sink = settings, envelope, history_sink
        self.errors: list[RowError] = []
        self.error_count = 0
        self.unusable: set[TemplateName] = set()
        self.location_roles: dict[str, str] = {}  # every location ID seen -> role (if valid)
        self.product_ids: set[str] = set()
        self.location_index: dict[str, int] = {}  # clean, within-envelope IDs only
        self.product_index: dict[str, int] = {}
        self.rows_seen: dict[TemplateName, int] = {}
        self.on_row: Callable[[TemplateName, int], None] | None = None  # progress hook

    # --- reporting --------------------------------------------------------------------------

    def report(self, file: TemplateName, line: int, column: str | None, code: ErrorCode,
               reason: str, fix: str, value: str | None = None) -> None:
        self.error_count += 1
        if len(self.errors) < self.envelope.max_reported_errors:
            self.errors.append(RowError(file=file, line=line, column=column, code=code,
                                        reason=reason, fix=fix, value=value))

    # --- driver -----------------------------------------------------------------------------

    def run(self, files: Mapping[TemplateName, BinaryIO]) -> ValidationReport:
        for name in REQUIRED_TEMPLATES:
            if name not in files:
                self.unusable.add(name)
                self.report(name, 1, None, "MALFORMED", f"{name}.csv is required and is missing",
                            f"Upload {name}.csv, starting from the blank template")
        as_of = self.settings.as_of_date or self._default_as_of(files)
        if as_of is None:
            for name in FILE_ORDER:  # still say why each file can't be read (e.g. UTF-16)
                if name in files:
                    for _ in self._records(name, files[name]):
                        pass
            if not self.unusable.intersection(HISTORY_FILES):  # else that file's error says why
                self.report("demand_history", 1, "date", "MALFORMED",
                            "no valid history date, so the as-of date can't be set",
                            "Add dated history rows, or enter the as-of date for the inventory")
            return ValidationReport(ok=False, errors=tuple(self.errors),
                                    error_count=self.error_count)
        self.as_of = as_of
        self.parsed = ParsedNetwork(as_of_date=as_of, files=frozenset(files))
        self._day_lines: dict[TemplateName, dict[int, array]] = {n: {} for n in HISTORY_FILES}
        self._donations: dict[tuple[str, str, date], list] = {}
        for name in FILE_ORDER:
            if name in files:
                getattr(self, f"_{name}")(self._records(name, files[name]))
        self.parsed.donation_history = [
            DonationDay(loc, prod, day, total, "; ".join(donors) or None)
            for (loc, prod, day), (total, donors) in self._donations.items()
        ]
        ok = self.error_count == 0
        return ValidationReport(ok=ok, errors=tuple(self.errors), error_count=self.error_count,
                                rows=self.parsed if ok else None)

    def _default_as_of(self, files: Mapping[TemplateName, BinaryIO]) -> date | None:
        """The day after the last valid history date (V1-SPEC §6.1). Reads the history files
        once more, so they must be seekable (BytesIO, or files on the imports volume)."""
        last: date | None = None
        for name in HISTORY_FILES:
            if name not in files:
                continue
            stream = files[name]
            for cells in self._records(name, stream, quiet=True):
                raw = cells[1].get("date", "")
                if ISO_DATE.fullmatch(raw):
                    try:
                        day = date.fromisoformat(raw)
                    except ValueError:
                        continue
                    last = day if last is None or day > last else last
            stream.seek(0)
        return None if last is None else last + timedelta(days=1)

    def _records(self, name: TemplateName, stream: BinaryIO, quiet: bool = False
                 ) -> Iterator[tuple[int, dict[str, str]]]:
        """Yield (line, trimmed cells by column) for each data row; report file-level errors."""
        state = {"bad_line": 0}

        def lines() -> Iterator[str]:
            for number, raw in enumerate(stream, 1):
                if number == 1 and raw.startswith(b"\xef\xbb\xbf"):
                    raw = raw[3:]
                try:
                    yield raw.decode("utf-8")
                except UnicodeDecodeError:
                    state["bad_line"] = number
                    return

        report = (lambda *a, **k: None) if quiet else self.report
        reader = csv.reader(lines())
        try:
            head = [cell.strip() for cell in next(reader)]
        except StopIteration:
            if state["bad_line"]:
                self._not_utf8(name, state["bad_line"], report)
            else:
                self.unusable.add(name)
                report(name, 1, None, "MALFORMED", f"{name}.csv is empty",
                       f"Start from the blank template; the first row is: {header(name)}")
            return
        except csv.Error as exc:
            self.unusable.add(name)
            report(name, 1, None, "MALFORMED", f"the header row can't be read: {exc}",
                   f"Start from the blank template; the first row is: {header(name)}")
            return
        if any("\x00" in cell for cell in head):  # e.g. UTF-16 without a BOM; PostgreSQL can't
            self.unusable.add(name)                # store the header in the error, so omit it
            report(name, 1, None, "MALFORMED",
                   "the header row contains a NUL character (0x00), so the file can't be read",
                   "Save the file as \"CSV UTF-8 (Comma delimited)\" and upload it again")
            return
        if not self._header_ok(name, head, report):
            self.unusable.add(name)
            return
        try:
            for cells in reader:
                if not any(cell.strip() for cell in cells):
                    continue  # blank lines, e.g. trailing ",,,," rows from a spreadsheet
                line = reader.line_num
                if len(cells) != len(head):
                    report(name, line, None, "MALFORMED",
                           f"expected {len(head)} fields, found {len(cells)}",
                           "Make the row match the header: one value per column, and quote "
                           "any value that contains a comma")
                    continue
                nul = next((col for col, cell in zip(head, cells, strict=True) if "\x00" in cell),
                           None)
                if nul is not None:  # valid UTF-8, but PostgreSQL text can't hold it (COPY fails)
                    report(name, line, nul, "MALFORMED",
                           "the value contains a NUL character (0x00), which can't be stored",
                           "Delete the hidden character from this cell, or re-save the file as "
                           "CSV UTF-8")
                    # Check the rest of the row without the NUL (one error per cell); the
                    # error above already means nothing is saved.
                    cells = [cell.replace("\x00", "") for cell in cells]
                yield line, dict(zip(head, (cell.strip() for cell in cells), strict=True))
        except csv.Error as exc:
            report(name, reader.line_num, None, "MALFORMED", f"the row can't be read: {exc}",
                   "Check the quotes on this row; a quoted value must end with a quote")
        if state["bad_line"]:
            self._not_utf8(name, state["bad_line"], report)

    def _not_utf8(self, name: TemplateName, line: int, report) -> None:
        self.unusable.add(name)
        report(name, line, None, "MALFORMED", "the file is not UTF-8 text",
               "Save the file as \"CSV UTF-8 (Comma delimited)\" and upload it again")

    def _header_ok(self, name: TemplateName, head: list[str], report) -> bool:
        known = dict(COLUMNS[name])
        unknown = [col for col in head if col not in known]
        missing = [col for col, required in COLUMNS[name] if required and col not in head]
        repeated = sorted({col for col in head if head.count(col) > 1})
        if not (unknown or missing or repeated):
            return True
        parts = ([f"unknown column(s): {', '.join(unknown)}"] if unknown else []) + (
            [f"missing required column(s): {', '.join(missing)}"] if missing else []) + (
            [f"repeated column(s): {', '.join(repeated)}"] if repeated else [])
        report(name, 1, (unknown or missing or repeated)[0], "MALFORMED", "; ".join(parts),
               f"Use the header row from the blank template: {header(name)}")
        return False

    # --- per-file rules ---------------------------------------------------------------------

    def _rows(self, name: TemplateName, records) -> Iterator[tuple[int, dict[str, str], "_Row"]]:
        for line, cells in records:
            self.rows_seen[name] = self.rows_seen.get(name, 0) + 1
            if self.on_row:
                self.on_row(name, line)
            row = _Row(self, name, line, cells)
            yield line, cells, row

    def _locations(self, records) -> None:
        seen: dict[str, int] = {}
        roles = ROLES_BY_MODE[self.settings.mode]
        for line, cells, row in self._rows("locations", records):
            location_id = row.id("location_id")
            role = row.cell("type").lower()
            if location_id is not None:
                if location_id in seen:
                    row.fail("location_id", "DUPLICATE",
                             f"location_id {location_id} is already on line {seen[location_id]}",
                             "Give each location its own location_id, or delete the repeated row")
                    continue
                seen[location_id] = line
                self.location_roles[location_id] = role
            if role not in roles:
                row.fail("type", "MALFORMED",
                         f"{cells['type'] or 'a blank type'} is not a "
                         f"{self.settings.mode.title()} location type",
                         f"Use {' or '.join(roles)}", cells["type"])
            name = row.required("name")
            street, city = row.required("street"), row.required("city")
            state = cells["state"].upper()
            if state not in US_STATES:
                row.fail("state", "MALFORMED",
                         f"{cells['state'] or 'blank'} is not a US state code; v1 supports US "
                         "addresses only (Census geocoding)",
                         "Use the two-letter US state code, e.g. FL", cells["state"])
            elif not re.fullmatch(r"\d{5}(-\d{4})?", cells["zip"]):
                row.fail("zip", "MALFORMED", "not a 5-digit US ZIP code",
                         "Use 5 digits (or ZIP+4), e.g. 32301. If a spreadsheet dropped a "
                         "leading zero, format the column as text", cells["zip"])
            lat = row.decimal("latitude", Decimal(-90), Decimal(90))
            lon = row.decimal("longitude", Decimal(-180), Decimal(180))
            if (cells.get("latitude", "") == "") != (cells.get("longitude", "") == ""):
                row.fail("longitude" if cells.get("latitude") else "latitude", "MALFORMED",
                         "only one of latitude and longitude is given",
                         "Give both latitude and longitude, or leave both blank to geocode")
            capacity = row.decimal("receiving_capacity_per_day", Decimal(0))
            poverty = row.rate("poverty_rate")
            snap = row.rate("snap_rate")
            if row.ok and len(self.location_index) >= self.envelope.max_locations:
                row.fail(None, "OVER_ENVELOPE",
                         f"more than {self.envelope.max_locations} locations "
                         f"(limit {self.envelope.max_locations})",
                         f"Keep at most {self.envelope.max_locations} locations in one network")
            if row.ok:
                self.location_index[location_id] = len(self.location_index)
                self.parsed.locations.append(ParsedLocation(
                    line, location_id, name, role, street, city, state, cells["zip"], lat, lon,
                    capacity, poverty, snap))

    def _products(self, records) -> None:
        seen: dict[str, int] = {}
        for line, cells, row in self._rows("products", records):
            product_id = row.id("product_id")
            if product_id is not None:
                if product_id in seen:
                    row.fail("product_id", "DUPLICATE",
                             f"product_id {product_id} is already on line {seen[product_id]}",
                             "Give each product its own product_id, or delete the repeated row")
                    continue
                seen[product_id] = line
                self.product_ids.add(product_id)
            name, unit = row.required("name"), row.required("unit")
            value = row.decimal("unit_value_usd", Decimal(0))
            # `high` is checked before the storage envelope, so every value over the limit,
            # however large, gets this error and fix (W2-06 A5).
            handling = row.decimal("handling_units_per_unit", Decimal(0),
                                   Decimal(MAX_HANDLING_UNITS), range_fix=(
                                       f"Enter a whole number from 1 to {MAX_HANDLING_UNITS}, "
                                       "or leave it blank to assume 1"))
            # Numeric(14, 6) stores anything smaller as 0, which the > 0 check refuses.
            if handling is not None and handling < Decimal("0.000001"):
                row.fail("handling_units_per_unit", "MALFORMED",
                         "must be a whole number greater than 0",
                         "Enter how many handling units one product unit takes, e.g. 1, or "
                         "leave it blank to assume 1", cells["handling_units_per_unit"])
            elif handling is not None and handling % 1:  # the freeze needs whole units
                row.fail("handling_units_per_unit", "FRACTIONAL",
                         "handling_units_per_unit must be a whole number",
                         "Enter a whole number of handling units per unit, e.g. 1 or 2, or "
                         "leave it blank to assume 1", cells["handling_units_per_unit"])
            if row.ok and len(self.product_index) >= self.envelope.max_products:
                row.fail(None, "OVER_ENVELOPE",
                         f"more than {self.envelope.max_products} products "
                         f"(limit {self.envelope.max_products})",
                         f"Keep at most {self.envelope.max_products} products in one network")
            if row.ok:
                self.product_index[product_id] = len(self.product_index)
                self.parsed.products.append(ParsedProduct(
                    line, product_id, name, unit, value,
                    handling if handling is not None else Decimal(1), handling is not None))

    def _inventory(self, records) -> None:
        seen: dict[tuple[str, str, str], int] = {}
        for line, _cells, row in self._rows("inventory", records):
            location_id, product_id = row.location("location_id"), row.product("product_id")
            batch_id = row.id("batch_id")
            if None not in (location_id, product_id, batch_id):
                key = (location_id, product_id, batch_id)
                if key in seen:
                    row.fail("batch_id", "DUPLICATE",
                             f"batch {batch_id} of {product_id} at {location_id} is already on "
                             f"line {seen[key]}",
                             "Give each batch its own batch_id, or delete the repeated row")
                    continue
                seen[key] = line
            quantity = row.quantity("quantity", blank_ok=False)
            expiry, non_expiring = row.expiry()
            received = row.iso_date("received_date")
            if row.ok and len(self.parsed.batches) >= self.envelope.max_batches:
                row.fail(None, "OVER_ENVELOPE",
                         f"more than {self.envelope.max_batches:,} batches "
                         f"(limit {self.envelope.max_batches:,})",
                         "Combine batches with the same product, location and expiry date")
            if row.ok:
                self.parsed.batches.append(ParsedBatch(
                    line, location_id, product_id, batch_id, quantity, expiry, non_expiring,
                    received))

    def _history(self, name: TemplateName, records) -> None:
        window = self.envelope.max_history_days
        for line, cells, row in self._rows(name, records):
            location_id, product_id = row.location("location_id"), row.product("product_id")
            day = row.iso_date("date", required=True)
            quantity = row.quantity("quantity", blank_ok=True)
            basis = None
            if name == "demand_history":
                basis = cells["basis"].lower()
                if basis not in ("demand", "sales"):
                    row.fail("basis", "MALFORMED", "basis must be demand or sales",
                             "Enter demand (requests or need) or sales (what was sold or "
                             "given out)", cells["basis"])
            if day is not None and day > self.as_of:
                row.fail("date", "AFTER_AS_OF_DATE",
                         f"{day} is after the as-of date {self.as_of} (no future history)",
                         f"Remove rows dated after {self.as_of}, or move the as-of date",
                         cells["date"])
            elif day is not None and (self.as_of - day).days > window:
                row.fail("date", "OVER_ENVELOPE",
                         f"{day} is more than {window} days before the as-of date {self.as_of} "
                         f"(limit {window} days)",
                         f"Keep only the last {window} days of history", cells["date"])
            if row.ok and name == "demand_history":
                first = self._first_line(name, location_id, product_id, day, line)
                if first:
                    row.fail("date", "DUPLICATE",
                             f"{location_id}, {product_id} on {day} is already on line {first}",
                             "Keep one row per location, product and date")
            if not row.ok:
                continue
            record = HistoryRow(line, location_id, product_id, day, quantity, basis,
                                cells.get("donor") or None)
            if basis == "sales":
                self.parsed.sales_basis_series.add((location_id, product_id))
            if self.history_sink is not None:
                self.history_sink(name, record)
            elif name == "demand_history":
                self.parsed.demand_history.append(record)
            else:  # donations are summed per receiving location × product × day (V1-SPEC §6.1)
                key = (location_id, product_id, day)
                total, donors = self._donations.setdefault(key, [0, []])
                # One blank row makes the day unknown: a partial sum would hide it (never zero).
                self._donations[key][0] = (None if total is None or quantity is None
                                           else total + quantity)
                if record.donor and record.donor not in donors:
                    donors.append(record.donor)

    def _demand_history(self, records) -> None:
        self._history("demand_history", records)

    def _donation_history(self, records) -> None:
        self._history("donation_history", records)

    def _first_line(self, name: TemplateName, location_id: str, product_id: str, day: date,
                    line: int) -> int:
        """Line of an earlier row with the same key, else 0. One fixed array per day keeps this
        bounded at the full envelope (≤ 90 days × 100 × 500 slots)."""
        if location_id not in self.location_index or product_id not in self.product_index:
            return 0  # an over-envelope or rejected ID is reported already
        slots = self._day_lines[name].get(day.toordinal())
        if slots is None:
            size = len(self.location_index) * len(self.product_index)
            slots = self._day_lines[name][day.toordinal()] = array("L", [0]) * size
        slot = self.location_index[location_id] * len(self.product_index)
        slot += self.product_index[product_id]
        if slots[slot]:
            return slots[slot]
        slots[slot] = line
        return 0

    def _routes(self, records) -> None:
        seen: dict[tuple[str, str], int] = {}
        located = {loc.location_id for loc in self.parsed.locations if loc.latitude is not None}
        for line, _cells, row in self._rows("routes", records):
            source, target = row.location("from_location_id"), row.location("to_location_id")
            if source is not None and source == target:
                row.fail("to_location_id", "MALFORMED", "a route can't start and end at the "
                         "same location", "Use two different location IDs")
            elif target is not None and self.location_roles.get(target) in (
                    "hub", "distribution_center"):
                row.fail("to_location_id", "MALFORMED",
                         f"{target} is a {self.location_roles[target].replace('_', ' ')}, and "
                         "hubs and distribution centers never receive transfers",
                         "Remove this row, or route to a pantry or store", target)
            if source is not None and target is not None:
                if (source, target) in seen:
                    row.fail("to_location_id", "DUPLICATE",
                             f"route {source} → {target} is already on line "
                             f"{seen[(source, target)]}", "Keep one row per route")
                    continue
                seen[(source, target)] = line
            days = row.quantity("travel_days", blank_ok=True)
            if days == 0:
                row.fail("travel_days", "MALFORMED", "travel_days must be at least 1",
                         "Enter whole days of at least 1 (a same-region transfer arrives the "
                         "next day), or leave it blank to estimate", "0")
            elif days is None and row.ok and not (
                    source in located and target in located):
                # A stored route always has travel_days; without coordinates there's no estimate.
                row.fail("travel_days", "MALFORMED",
                         f"travel_days is blank and {source} → {target} can't be estimated "
                         "without coordinates for both locations",
                         "Enter travel_days in whole days, or add latitude and longitude for "
                         "both locations in locations.csv")
            cost = row.decimal("cost_per_handling_unit", Decimal(0))
            capacity = row.decimal("capacity_per_batch", Decimal(0))
            disabled = row.boolean("disabled")
            if row.ok:
                self.parsed.routes.append(ParsedRoute(
                    line, source, target, days, cost, capacity, disabled))

    def _inbound(self, records) -> None:
        horizon_end = self.as_of + timedelta(days=HORIZON_DAYS)
        for line, cells, row in self._rows("inbound", records):
            location_id, product_id = row.location("location_id"), row.product("product_id")
            quantity = row.quantity("quantity", blank_ok=False)
            if quantity == 0:
                row.fail("quantity", "MALFORMED", "an arrival must bring at least 1 unit",
                         "Enter a positive whole number, or delete the row", "0")
            arrival = row.iso_date("arrival_date", required=True)
            if arrival is not None and arrival <= self.as_of:
                row.fail("arrival_date", "MALFORMED",
                         f"{arrival} is not after the as-of date {self.as_of}",
                         "Stock that has already arrived belongs in inventory.csv; inbound "
                         "rows are future arrivals", cells["arrival_date"])
            expiry, non_expiring = row.expiry()
            source = cells.get("source", "").lower() or None
            if source is not None and source not in INBOUND_SOURCES:
                row.fail("source", "MALFORMED", f"{cells['source']} is not a known source",
                         f"Use one of {', '.join(INBOUND_SOURCES)}, or leave it blank",
                         cells["source"])
            if row.ok:
                self.parsed.inbound.append(ParsedInbound(
                    line, location_id, product_id, quantity, arrival, expiry, non_expiring,
                    source, cells.get("reference") or None, arrival <= horizon_end))


class _Row:
    """Cell parsers for one row. Each records its error and returns None on a bad cell."""

    __slots__ = ("v", "file", "line", "cells", "ok")

    def __init__(self, validator: Validator, file: TemplateName, line: int,
                 cells: dict[str, str]):
        self.v, self.file, self.line, self.cells, self.ok = validator, file, line, cells, True

    def fail(self, column: str | None, code: ErrorCode, reason: str, fix: str,
             value: str | None = None) -> None:
        self.ok = False
        self.v.report(self.file, self.line, column, code, reason, fix, value)

    def cell(self, column: str) -> str:
        return self.cells.get(column, "")

    def _parse(self, column: str, parse):
        raw = self.cell(column)
        try:
            return parse(raw)
        except _Bad as bad:
            self.fail(column, bad.code, bad.reason, bad.fix, raw)
            return None

    def required(self, column: str) -> str | None:
        def parse(raw: str) -> str:
            if not raw:
                raise _Bad("MALFORMED", "required value is blank", f"Enter a {column}")
            return raw
        return self._parse(column, parse)

    def id(self, column: str) -> str | None:
        def parse(raw: str) -> str:
            if not raw:
                raise _Bad("MALFORMED", "required value is blank", f"Enter a {column}")
            if len(raw) > ID_MAX_LENGTH:
                raise _Bad("MALFORMED", f"longer than {ID_MAX_LENGTH} characters",
                           f"Shorten the {column} to at most {ID_MAX_LENGTH} characters")
            return raw
        return self._parse(column, parse)

    def location(self, column: str) -> str | None:
        return self._reference(column, "locations", self.v.location_roles)

    def product(self, column: str) -> str | None:
        return self._reference(column, "products", self.v.product_ids)

    def _reference(self, column: str, source: TemplateName, known) -> str | None:
        value = self.id(column)
        if value is None or source in self.v.unusable or value in known:
            return value
        self.fail(column, "UNKNOWN_ID", f"{value} is not in {source}.csv",
                  f"Add {value} to {source}.csv, or correct the ID (IDs are case-sensitive)",
                  value)
        return None

    def quantity(self, column: str, blank_ok: bool) -> int | None:
        def parse(raw: str) -> int | None:
            if not raw:
                if blank_ok:
                    return None
                raise _Bad("MALFORMED", "required value is blank",
                           "Enter 0 or a positive whole number")
            fix = BLANK_OK_QUANTITY_FIX if blank_ok else "Enter 0 or a positive whole number"
            if not DIGITS.fullmatch(raw):
                try:
                    number = Decimal(raw)
                except InvalidOperation:
                    raise _Bad("MALFORMED", "not a number", fix) from None
                if not number.is_finite():
                    raise _Bad("MALFORMED", "not a number", fix)
                if number < 0:
                    raise _Bad("NEGATIVE", f"{column} can't be negative", fix)
                raise _Bad("FRACTIONAL", f"{column} must be a whole number",
                           "Round to a whole number of units (digits only, no decimal point)")
            digits = raw.lstrip("0") or "0"  # int() refuses over 4,300 digits: size it first
            if len(digits) > len(str(MAX_QUANTITY)) or int(digits) > MAX_QUANTITY:
                shown = (f"{int(digits):,}" if len(digits) <= 18
                         else f"a {len(digits):,}-digit number")
                raise _Bad("OVER_ENVELOPE",
                           f"{shown} is above the planning limit of {MAX_QUANTITY:,} units "
                           "per row", f"Split it into rows of at most {MAX_QUANTITY:,} units, "
                           "or use a larger unit (e.g. pallets instead of cases)")
            return int(digits)
        return self._parse(column, parse)

    def decimal(self, column: str, low: Decimal, high: Decimal | None = None,
                range_fix: str | None = None) -> Decimal | None:
        def parse(raw: str) -> Decimal | None:
            if not raw:
                return None
            try:
                number = Decimal(raw)
            except InvalidOperation:
                raise _Bad("MALFORMED", "not a number", "Enter a plain number, e.g. 12.5, or "
                           "leave the cell blank") from None
            if not number.is_finite():
                raise _Bad("MALFORMED", "not a number", "Enter a plain number, or leave the "
                           "cell blank")
            if number < low and low == 0:
                raise _Bad("NEGATIVE", f"{column} can't be negative",
                           "Enter 0 or a positive number, or leave the cell blank")
            if number < low or (high is not None and number > high):
                raise _Bad("MALFORMED", f"must be between {low} and {high}",
                           range_fix or f"Enter a value from {low} to {high}")
            if number > MAX_DECIMAL:
                raise _Bad("OVER_ENVELOPE",
                           f"{column} is above the largest value v1 stores ({MAX_DECIMAL:,})",
                           f"Enter at most {MAX_DECIMAL:,}, or use a larger unit")
            return number
        return self._parse(column, parse)

    def rate(self, column: str) -> Decimal | None:
        # Above 1 is most likely a percentage, so the fix says how to write it as a fraction.
        return self.decimal(column, Decimal(0), Decimal(1), range_fix=(
            "Enter the rate as a fraction from 0 to 1, e.g. 0.125 for 12.5%"))

    def iso_date(self, column: str, required: bool = False) -> date | None:
        def parse(raw: str) -> date | None:
            if not raw:
                if required:
                    raise _Bad("MALFORMED", "required value is blank", DATE_FIX)
                return None
            if ISO_DATE.fullmatch(raw):
                try:
                    return date.fromisoformat(raw)
                except ValueError:
                    pass
            raise _Bad("MALFORMED", "not a valid date in YYYY-MM-DD form", DATE_FIX)
        return self._parse(column, parse)

    def boolean(self, column: str) -> bool:
        def parse(raw: str) -> bool:
            if raw.lower() in ("", "false"):
                return False
            if raw.lower() == "true":
                return True
            raise _Bad("MALFORMED", "must be true, false or blank", "Enter true, false, or "
                       "leave the cell blank")
        return bool(self._parse(column, parse))

    def expiry(self) -> tuple[date | None, bool]:
        expiry = self.iso_date("expiry_date")
        non_expiring = self.boolean("non_expiring")
        if self.cell("expiry_date") and non_expiring:
            self.fail("non_expiring", "MALFORMED", "both expiry_date and non_expiring=true "
                      "are given", "Keep the expiry date, or clear it if the item doesn't "
                      "expire", self.cell("non_expiring"))
        elif not self.cell("expiry_date") and not non_expiring:
            self.fail("expiry_date", "MISSING_EXPIRY", "no expiry_date and not marked "
                      "non_expiring", "Enter the expiry date (YYYY-MM-DD), or "
                      "non_expiring=true for items that don't expire")
        return expiry, non_expiring
