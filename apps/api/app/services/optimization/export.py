"""Plan export CSV; simulated, changes no stock (W1-S07, V1-SPEC §6.5).

Pure: reads the saved comparison and its frozen scenario, writes text. Nothing is reserved,
dispatched or recorded.
"""

import csv
import io
from collections.abc import Sequence

from app.schemas.v1_planning import NON_ADDITIVE_LABEL, AllocationMethod, SavedComparisonV3
from app.services.optimization.actions import decision_actions, units_label
from app.services.optimization.methods import OPTIMIZING
from app.services.optimization.v3 import PER_PRODUCT_LABEL

SIMULATED_NOTE = "simulated plan; no stock was reserved or moved"
NO_INBOUND_NOTE = "no scheduled deliveries provided"
CAPACITY_NOTE = "capacity not provided — no limit assumed"
FORMULA_START = ("=", "+", "-", "@", "\t", "\r")
COLUMNS = (
    "scenario_id",
    "scenario_hash",
    "method",
    "network_mode",
    "product",
    "unit",
    "quantity",
    "from",
    "to",
    "ship_date",
    "arrival_date",
    "why",
    "effect",
    "note",
)


def export_plan_csv(
    comparison: SavedComparisonV3,
    method: AllocationMethod,
    action_ids: Sequence[str],
    *,
    scenario,
) -> str:
    """CSV of the selected actions of one verified method; unknown action ids raise KeyError."""
    result = comparison.result
    if scenario.network_id != comparison.network_id or scenario.mode != result.mode:
        raise ValueError("SCENARIO_MISMATCH")
    chosen = next((m for m in result.methods if m.method == method), None)
    if chosen is None:
        raise KeyError(method)
    if not chosen.verified:
        raise ValueError("RESULT_NOT_VERIFIED")
    actions = {
        a.id: a for a in decision_actions(scenario, chosen, comparison_id=comparison.id).actions
    }
    transfers = {t.id: t for t in chosen.transfers}
    missing = [i for i in action_ids if i not in actions]
    if missing:
        raise KeyError(", ".join(missing))
    products = {p.id: p for p in scenario.products}
    names = {loc.id: loc.name for loc in scenario.locations}
    notes = [SIMULATED_NOTE]
    if CAPACITY_NOTE in scenario.assumptions:
        notes.append(CAPACITY_NOTE)
    if not scenario.inbound_file_provided:
        notes.append(NO_INBOUND_NOTE)
    note = "; ".join(notes)
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(COLUMNS)
    solved = {p.product_id: p for p in chosen.products}
    for action_id in dict.fromkeys(action_ids):
        a, t = actions[action_id], transfers[action_id]
        product = products[t.product_id]
        row_note = note
        if method in OPTIMIZING:  # W0-optimizer-decomposition 4: say how, and that it was solved
            solve = solved[t.product_id]
            gap = f" (gap {solve.gap})" if solve.gap else ""
            row_note = f"{note}; {PER_PRODUCT_LABEL}; product solved {solve.native_status}{gap}"
        writer.writerow(
            tuple(
                cell(value)
                for value in (
                    result.scenario_id,
                    result.scenario_hash,
                    method,
                    result.mode,
                    product.name,
                    product.unit,
                    t.quantity,
                    names[t.from_location_id],
                    names[t.to_location_id],
                    t.ship_date.isoformat(),
                    t.arrival_date.isoformat(),
                    a.why_text,
                    effect_text(a.effect, product.unit),
                    row_note,
                )
            )
        )
    return out.getvalue()


def cell(value):
    """Names come from the user's import: a leading ' keeps = + - @ from starting a formula."""
    return f"'{value}" if isinstance(value, str) and value.startswith(FORMULA_START) else value


def effect_text(effect, unit: str) -> str:
    def amount(n):
        return f"{n:+d} {units_label(unit, abs(n))}"

    parts = [
        f"sender unmet {amount(effect.sender_unmet_delta)}",
        f"receiver unmet {amount(effect.receiver_unmet_delta)}",
        f"expired {amount(effect.expired_delta)}",
    ]
    if effect.usd_delta is not None:
        parts.append(f"USD {effect.usd_delta}")
    return f"{'; '.join(parts)} ({NON_ADDITIVE_LABEL})"
