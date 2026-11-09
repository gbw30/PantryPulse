"""A generated sample network: its import settings and one CSV text per template (W3-P01/P02).

Samples are fictional, dated relative to the day they are generated (V1-SPEC §8), and imported
through the same importer as a user's files, never written to the tables directly."""

import csv
import io
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import date

from app.schemas.v1_networks import TemplateName
from app.schemas.v1_planning import NetworkMode
from app.services.imports.columns import COLUMNS

TIMEZONE = "America/New_York"
HISTORY_DAYS = 90
NO_STREET = "No street address (sample)"  # city-level coordinates only; no real buildings


@dataclass(frozen=True)
class SampleNetwork:
    name: str
    mode: NetworkMode
    as_of_date: date
    files: dict[TemplateName, str]
    timezone: str = TIMEZONE


def to_csv(name: TemplateName, rows: Iterable[Mapping[str, object]]) -> str:
    """The template's header order; a missing or None cell is written blank."""
    out = io.StringIO()
    writer = csv.DictWriter(out, [column for column, _ in COLUMNS[name]], lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()
