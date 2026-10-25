"""Pure stock command validation and canonical retry identity."""

from uuid import UUID

import pytest
from pydantic import ValidationError

from app.schemas.stock import AdjustStock, LotDelta, StockActor, VersionExpectation
from app.services.inventory.stock import command_hash


def command(deltas):
    return AdjustStock(idempotency_key="key", reason="Correction", source_reference="count-note",
                       changes=deltas, expected_versions=(VersionExpectation(
                           site_id=UUID(int=1), product_id=UUID(int=2), version=1),))


@pytest.mark.parametrize("value", [0, True, 1.1, "1", -(2**63), 2**63])
def test_adjustment_requires_nonzero_exact_bounded_integer(value):
    with pytest.raises(ValidationError):
        LotDelta(lot_id=UUID(int=3), delta=value)


def test_duplicate_lot_targets_are_rejected():
    delta = LotDelta(lot_id=UUID(int=3), delta=-1)
    with pytest.raises(ValidationError):
        command((delta, delta))


def test_hash_is_order_independent_but_actor_and_values_matter():
    actor = StockActor(organization_id=UUID(int=4), actor="presenter")
    a = LotDelta(lot_id=UUID(int=5), delta=2)
    b = LotDelta(lot_id=UUID(int=6), delta=-1)
    assert command_hash(actor, command((a, b))) == command_hash(actor, command((b, a)))
    assert command_hash(actor, command((a,))) != command_hash(actor, command((b,)))
    other = StockActor(organization_id=UUID(int=4), actor="other-presenter")
    assert command_hash(actor, command((a,))) != command_hash(other, command((a,)))
