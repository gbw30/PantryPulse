"""Fictional sample networks, loaded by the local seed on every start.

W0-05 ships this stub; `w3-samples` implements it in W3-P04. It must stay idempotent and must
never reset or delete data.
"""

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class SeedReport:
    loaded: tuple[str, ...] = ()


def ensure_samples(session, today: date) -> SeedReport:
    return SeedReport(loaded=())
