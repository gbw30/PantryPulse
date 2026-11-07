"""Decision actions: action, why, and the remove-one effect (W1-S06).

W0-08 stub: frozen signatures; the owning lane task replaces each body."""

from app.schemas.v1_planning import ActionEffect, DecisionActions, MethodResult, ORInputV3
from app.services.v1_errors import NotImplementedV1


def decision_actions(scenario: ORInputV3, result: MethodResult) -> DecisionActions:
    raise NotImplementedV1("W1-S06")


def remove_one_effect(scenario: ORInputV3, result: MethodResult, transfer_id: str) -> ActionEffect:
    raise NotImplementedV1("W1-S06")
