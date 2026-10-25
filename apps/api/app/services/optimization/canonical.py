"""Canonical exact operational identity, separate from forecast-handoff identity."""

import hashlib
import json
from datetime import UTC, date, datetime
from decimal import Decimal
from enum import Enum
from fractions import Fraction
from uuid import UUID

from pydantic import BaseModel

# OR-DEC-009 [PROVISIONAL]: sort identity collections, preserve dated/loading order.
_UNORDERED = {
    "sites",
    "products",
    "forecasts",
    "inventory",
    "confirmed_arrivals",
    "routes",
    "reserves",
    "vulnerability_attributes",
    "source_refs",
    "scores",
    "coefficients",
    "costs",
    "modifiers",
    "demand",
    "waste_references",
    "decision_ids",
}


def _normalize(value, name=""):
    if isinstance(value, BaseModel):
        return _normalize(value.model_dump(mode="python"), name)
    if isinstance(value, dict):
        return {str(k): _normalize(v, str(k)) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        values = [_normalize(v) for v in value]
        if name in _UNORDERED:
            values.sort(key=lambda v: json.dumps(v, sort_keys=True, separators=(",", ":")))
        return values
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("Canonical instants require timezone")
        return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise ValueError("Nonfinite canonical decimal")
        text = format(value, "f")
        return (text.rstrip("0").rstrip(".") if "." in text else text) if value else "0"
    if isinstance(value, Fraction):
        return {"numerator": value.numerator, "denominator": value.denominator}
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, float):
        raise ValueError("Float is forbidden in canonical operational payload")
    if value is None or isinstance(value, (str, int, bool)):
        return value
    raise ValueError(f"Unsupported canonical value {type(value).__name__}")


def canonical_bytes(payload) -> bytes:
    return json.dumps(
        _normalize(payload),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def operational_hash(payload) -> str:
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()
