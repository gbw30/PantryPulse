"""Stable draft identifiers. Their selected status does not close backend OPEN topics."""

DECISION_IDS = tuple(f"OR-DEC-{i:03d}" for i in range(1, 21))
POLICY_VERSION = "or-draft-1.1"
DECISION_STATUS = "PROVISIONAL_WITH_EXTERNAL_HANDOFFS"
EXTERNAL_DECISIONS = ("OR-DEC-012",)
WITHDRAWN_DECISIONS = ("OR-DEC-014",)
