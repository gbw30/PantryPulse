"""Pure scenario canonicalization and supplied-source freshness comparisons.

No persistence, live-source discovery, stock mutation, admission or allocation.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal

from app.schemas.scenario import OperationalScenario, SourceReference


@dataclass(frozen=True, slots=True)
class FrozenScenario:
    inputs: OperationalScenario
    canonical_json: str
    content_hash: str


@dataclass(frozen=True, slots=True)
class FreshnessChange:
    kind: str
    key: str
    reason: Literal["MISSING", "ADDED", "CHANGED"]


@dataclass(frozen=True, slots=True)
class FreshnessReport:
    changes: tuple[FreshnessChange, ...]
    window_elapsed: bool

    @property
    def is_stale(self) -> bool:
        return bool(self.changes) or self.window_elapsed


def _decimal_text(value: Decimal) -> str:
    # Scientific decimal strings: exact, context-independent and bounded by
    # coefficient length, including tiny values with very large negative exponents.
    sign, digits, exponent = value.as_tuple()
    digits = list(digits)
    if not any(digits):
        return "0"
    while digits[-1] == 0:
        digits.pop()
        exponent += 1
    return ("-" if sign else "") + "".join(str(d) for d in digits) + f"e{exponent}"


def freeze_scenario(inputs: OperationalScenario) -> FrozenScenario:
    if not isinstance(inputs, OperationalScenario):
        raise TypeError("freeze requires OperationalScenario")
    checked = OperationalScenario.model_validate(inputs.model_dump(mode="python"))
    payload = checked.model_dump(mode="json")
    for field, key in (
        ("sites", "site_id"), ("products", "product_id"), ("routes", "route_id"),
        ("forecasts", "forecast_id"),
        ("excluded_sites", "entity_id"), ("excluded_products", "entity_id")
    ):
        payload[field].sort(key=lambda item: item[key])
    for field in ("network_site_ids", "network_product_ids"):
        payload[field].sort()
    payload["sources"].sort(key=lambda item: (item["kind"], item["key"]))
    for site in payload["sites"]:
        site["receiving_capacity"].sort(key=lambda item: item["day"])
        site["reserves"].sort(key=lambda item: (item["product_id"], item["day"]))
    for route in payload["routes"]:
        route["unit_costs"].sort(key=lambda item: item["product_id"])
    payload["series"].sort(key=lambda item: (item["site_id"], item["product_id"]))
    for series in payload["series"]:
        original = next(item for item in checked.series
                        if str(item.site_id) == series["site_id"]
                        and str(item.product_id) == series["product_id"])
        series["lots"].sort(key=lambda item: item["lot_id"])
        series["commitments"].sort(key=lambda item: item["commitment_id"])
        by_id = {str(lot.lot_id): lot for lot in original.lots}
        for lot in series["lots"]:
            lot["available_at"] = by_id[lot["lot_id"]].available_at.astimezone(UTC).isoformat()
        for point, original_point in zip(series["demand"], original.demand, strict=True):
            point["estimate"] = _decimal_text(original_point.estimate)
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False)
    canonical = OperationalScenario.model_validate_json(encoded)
    return FrozenScenario(canonical, encoded, hashlib.sha256(encoded.encode("utf-8")).hexdigest())


def assess_freshness(
    historical: FrozenScenario, current_sources: tuple[SourceReference, ...], *, as_of_day: date
) -> FreshnessReport:
    """Compare explicitly supplied current dependency tokens; never read latest DB.

    The caller must enumerate the whole relevant scope, including membership and
    newly added lots/supplies/commitments. Partial reads cannot prove freshness.
    """
    if not isinstance(as_of_day, date) or isinstance(as_of_day, datetime):
        raise TypeError("as_of_day must be an explicit planning-calendar date")
    if freeze_scenario(historical.inputs) != historical:
        raise ValueError("historical scenario fingerprint does not match its inputs")
    previous = {(ref.kind, ref.key): (ref.version, ref.content_hash)
                for ref in historical.inputs.sources}
    current = {}
    for supplied in current_sources:
        ref = SourceReference.model_validate(supplied.model_dump())
        key = (ref.kind, ref.key)
        if key in current:
            raise ValueError("duplicate current source identity")
        current[key] = (ref.version, ref.content_hash)
    changes = []
    for kind, key in sorted(previous.keys() | current.keys()):
        identity = (kind, key)
        if identity not in current:
            reason = "MISSING"
        elif identity not in previous:
            reason = "ADDED"
        elif previous[identity] != current[identity]:
            reason = "CHANGED"
        else:
            continue
        changes.append(FreshnessChange(kind, key, reason))
    return FreshnessReport(tuple(changes), as_of_day > historical.inputs.allocation_start)
