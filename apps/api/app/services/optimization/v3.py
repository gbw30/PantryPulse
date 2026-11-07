"""Shared or-input-v3 rules: dates, roles, eligible routes, FEFO packing and transfer identity.

Pure and solver-free: the projection, the independent verifier, the heuristics and the CP-SAT
builder all read the same rules from here (data/demo/or-v3/README.md "Rules").
"""

import hashlib
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from app.schemas.v1_planning import BatchV3, ORInputV3, RouteV3, TransferV3

HORIZON = 7
K_NEAREST = 10  # senders kept per receiver and product (V1-SPEC §12 item 1, spike S1)
RECEIVER_ROLES = frozenset({"pantry", "store"})
HUB_ROLES = frozenset({"hub", "distribution_center"})
STARVED_LABEL = "capacity share too small to move one unit"
PER_PRODUCT_LABEL = "optimized per product, with shared capacity split in advance"

RouteKey = tuple[str, str, str]  # (product_id, from_location_id, to_location_id)


def dates(s: ORInputV3) -> tuple[date, ...]:
    return tuple(s.first_planning_date + timedelta(days=i) for i in range(HORIZON))


def window_days(s: ORInputV3) -> int:
    """Days in which a transferred unit must be consumed: Pantry BD-51 window, Retail all 7."""
    return HORIZON if s.mode == "RETAIL" else s.planning_days  # CR-w1-solver-1


def transfer_id(product_id: str, from_id: str, to_id: str) -> str:
    digest = hashlib.sha256(f"{product_id}\x1f{from_id}\x1f{to_id}".encode()).hexdigest()
    return f"t-{digest[:20]}"


def usd(value: str | None) -> Decimal | None:
    return None if value is None else Decimal(value)


def route_allowed(s: ORInputV3, route: RouteV3) -> bool:
    """Topology (mode, roles) plus arrival inside the consumption window."""
    roles = {loc.id: loc.role for loc in s.locations}
    if roles[route.to_location_id] not in RECEIVER_ROLES:
        return False  # hubs and DCs never receive
    if s.transfer_mode == "HUB_ONLY" and roles[route.from_location_id] not in HUB_ROLES:
        return False
    return route.travel_days < window_days(s)


def eligible(batch: BatchV3, arrival: date) -> bool:
    return batch.expiry_date is None or batch.expiry_date >= arrival


def fefo_key(expiry: date | None, available: date, ident: str):
    return (expiry or date.max, available, ident)


@dataclass(frozen=True)
class Candidate:
    """One mode-allowed route for one product, in the sender's frozen loading order."""

    product_id: str
    route: RouteV3
    arrival: date
    batches: tuple[BatchV3, ...]  # eligible on-hand sender batches, FEFO

    @property
    def key(self) -> RouteKey:
        return (self.product_id, self.route.from_location_id, self.route.to_location_id)

    @property
    def id(self) -> str:
        return transfer_id(*self.key)


def candidates(s: ORInputV3, product_id: str, routes=None, k=None) -> tuple[Candidate, ...]:
    """Frozen loading order per sender: longest travel first, then destination id (OR-DEC-004).

    Only routes from a sender holding eligible stock count, and each receiver keeps its k nearest
    such senders (candidates.k_nearest; default K_NEAREST). Packing and the verifier use the same
    candidate set, so a plan on any other route is rejected as ROUTE_NOT_ALLOWED.
    """
    from app.services.optimization.candidates import k_nearest

    first = s.first_planning_date
    held = defaultdict(list)
    for b in s.batches:
        if b.product_id == product_id:
            held[b.location_id].append(b)
    found = {}
    for r in s.routes if routes is None else routes:
        if not route_allowed(s, r):
            continue
        arrival = first + timedelta(days=r.travel_days)
        lots = sorted(
            (b for b in held[r.from_location_id] if eligible(b, arrival)),
            key=lambda b: fefo_key(b.expiry_date, first, b.id),
        )
        if lots:
            found[id(r)] = Candidate(product_id, r, arrival, tuple(lots))
    kept = k_nearest([c.route for c in found.values()], K_NEAREST if k is None else k)
    return tuple(
        sorted(
            (found[id(r)] for r in kept),
            key=lambda c: (c.route.from_location_id, -c.route.travel_days, c.route.to_location_id),
        )
    )


@dataclass(frozen=True)
class Packed:
    transfer: TransferV3
    splits: tuple[tuple[str, int], ...]  # (batch_id, units) drawn FEFO


def pack(s: ORInputV3, quantities: Mapping[RouteKey, int]) -> tuple[Packed, ...]:
    """Draw each positive route quantity from the sender's batches, FEFO in loading order.

    Raises ValueError("ROUTE_NOT_ALLOWED" / "SOURCE_OVERDRAWN") when the quantities cannot be
    packed. The CP model encodes the same chain, so its plans always pack.
    """
    wanted = {k: q for k, q in quantities.items() if q}
    if any(q < 0 for q in wanted.values()):
        raise ValueError("NEGATIVE_QUANTITY")
    left = {b.id: b.quantity for b in s.batches}
    packed, seen = [], set()
    for product_id in sorted({k[0] for k in wanted}):
        for c in candidates(s, product_id):
            if c.key not in wanted:
                continue
            seen.add(c.key)
            need, splits = wanted[c.key], []
            for b in c.batches:
                take = min(left[b.id], need)
                if take:
                    left[b.id] -= take
                    need -= take
                    splits.append((b.id, take))
            if need:
                raise ValueError("SOURCE_OVERDRAWN")
            packed.append(
                Packed(
                    TransferV3(
                        id=c.id,
                        product_id=product_id,
                        from_location_id=c.route.from_location_id,
                        to_location_id=c.route.to_location_id,
                        quantity=wanted[c.key],
                        ship_date=s.first_planning_date,
                        arrival_date=c.arrival,
                        batch_ids=tuple(b for b, _ in splits),
                    ),
                    tuple(splits),
                )
            )
    if seen != set(wanted):
        raise ValueError("ROUTE_NOT_ALLOWED")
    return tuple(packed)


def quantities_of(transfers) -> dict[RouteKey, int]:
    out: dict[RouteKey, int] = {}
    for t in transfers:
        key = (t.product_id, t.from_location_id, t.to_location_id)
        if key in out:
            raise ValueError("DUPLICATE_TRANSFER")
        out[key] = t.quantity
    return out
