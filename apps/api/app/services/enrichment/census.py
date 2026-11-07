"""Census batch geocoder client and the bundled ACS 5-year tract table (W1-D06).

The geocoder is the S5 endpoint: free, no key, one multipart POST for the whole batch, a
CSV answer in any order with longitude first. An HTML page, a transport error or a missing
row is an outage (CensusUnavailable): the caller marks fields unknown and offers a retry.
ACS rates come from the bundled table the lead generates (CR-w1-data-1, option A)."""

import csv
import functools
import gzip
import io
import json
import urllib.request
import uuid
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/geographies/addressbatch"
FORM = {"benchmark": "Public_AR_Current", "vintage": "Current_Current"}
TIMEOUT_S = 120
COORDINATE = Decimal("0.000001")
RATE = Decimal("0.00001")
MATCH_STATUSES = ("Exact", "Non_Exact")

Transport = Callable[[urllib.request.Request], bytes]


class CensusUnavailable(Exception):
    """The geocoder did not answer with the expected CSV."""


@dataclass(frozen=True, slots=True)
class Address:
    location_id: str
    street: str
    city: str
    state: str
    zip: str

    def text(self) -> str:
        return f"{self.street}, {self.city}, {self.state} {self.zip}"


@dataclass(frozen=True, slots=True)
class Geocode:
    location_id: str
    status: str  # Exact | Non_Exact | No_Match | Tie
    matched_address: str | None = None
    latitude: Decimal | None = None
    longitude: Decimal | None = None
    tract_geoid: str | None = None  # 11 characters: state, county, tract


def urlopen_transport(request: urllib.request.Request) -> bytes:
    with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:  # noqa: S310
        return response.read()


class CensusClient:
    def __init__(self, transport: Transport = urlopen_transport):
        self.transport = transport

    def geocode(self, addresses: Sequence[Address]) -> dict[str, Geocode]:
        """Geocode every address in one batch (the envelope caps a network at 100)."""
        if not addresses:
            return {}
        rows = io.StringIO()
        writer = csv.writer(rows, lineterminator="\n")
        for position, a in enumerate(addresses, start=1):
            writer.writerow((position, a.street, a.city, a.state, a.zip))
        try:
            body = self.transport(_multipart(rows.getvalue()))
            return _parse(body.decode("utf-8"), addresses)
        except CensusUnavailable:
            raise
        except (OSError, UnicodeDecodeError, ValueError) as error:  # URLError is an OSError
            raise CensusUnavailable(
                f"Census geocoder unavailable: {type(error).__name__}") from error


def _multipart(address_file: str) -> urllib.request.Request:
    boundary = uuid.uuid4().hex
    parts = [f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'
             for name, value in FORM.items()]
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="addressFile"; '
                 f'filename="addresses.csv"\r\nContent-Type: text/csv\r\n\r\n{address_file}\r\n')
    parts.append(f"--{boundary}--\r\n")
    return urllib.request.Request(
        GEOCODER_URL, data="".join(parts).encode(), method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})


def _parse(text: str, addresses: Sequence[Address]) -> dict[str, Geocode]:
    results: dict[str, Geocode] = {}
    for row in csv.reader(io.StringIO(text)):
        if not row:
            continue
        if len(row) < 3 or not row[0].isdigit() or not 1 <= int(row[0]) <= len(addresses):
            raise CensusUnavailable("Census geocoder answered with something other than CSV")
        location_id = addresses[int(row[0]) - 1].location_id
        if row[2] == "Match" and len(row) >= 12 and row[3] in MATCH_STATUSES:
            lon, lat = (Decimal(v).quantize(COORDINATE) for v in row[5].split(","))
            results[location_id] = Geocode(location_id, row[3], row[4], lat, lon,
                                           row[8] + row[9] + row[10])
        else:
            results[location_id] = Geocode(location_id, row[3] if row[2] == "Match" else row[2])
    if len(results) != len(addresses):
        raise CensusUnavailable("Census geocoder answered for only some addresses")
    return results


@dataclass(frozen=True, slots=True)
class AcsTable:
    year: int
    fetched_at: datetime
    counts: dict[str, tuple[str, str, str, str]]

    def rates(self, geoid: str) -> tuple[Decimal | None, Decimal | None]:
        """(poverty_rate, snap_rate); an unpublished count or a zero universe stays None."""
        row = self.counts.get(geoid)
        if row is None:
            return None, None
        return _rate(row[1], row[0]), _rate(row[3], row[2])

    def source(self, geoid: str) -> str:
        return f"ACS 5-year {self.year}, tract {geoid}"


def _rate(part: str, whole: str) -> Decimal | None:
    try:
        numerator, denominator = Decimal(part), Decimal(whole)
    except InvalidOperation:  # an empty cell: not published
        return None
    if denominator <= 0 or not 0 <= numerator <= denominator:
        return None
    return (numerator / denominator).quantize(RATE)


BUNDLED_ACS = Path(__file__).parent / "data" / "acs5-2024-tracts.csv.gz"


@functools.cache
def default_acs() -> AcsTable | None:
    """The bundled whole-US table, or None until the lead's file is installed."""
    try:
        return load_acs(BUNDLED_ACS)
    except FileNotFoundError:
        return None


def load_acs(path: Path) -> AcsTable:
    """Read `<name>.csv.gz` and its `<name>.json` metadata (the CR-w1-data-1 format)."""
    meta = json.loads(path.with_suffix("").with_suffix(".json").read_text())
    with gzip.open(path, "rt", encoding="utf-8", newline="") as handle:
        reader = csv.reader(handle)
        next(reader)  # geoid,poverty_universe,poverty_below,snap_households,snap_received
        counts = {row[0]: (row[1], row[2], row[3], row[4]) for row in reader if row}
    return AcsTable(int(meta["vintage"][-4:]),
                    datetime.fromisoformat(meta["generated_at"].replace("Z", "+00:00")), counts)
