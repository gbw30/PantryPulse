"""Containment evidence for attempts left by a lost supervisor (WQ-03, ADR 0004 A1)."""

from typing import Any, Protocol

from app.repositories.jobs import RecoveryItem
from app.workers.process_driver import BoundaryIdentity


class ForeignCleanup(Protocol):
    def cleanup_foreign(self, identity: BoundaryIdentity, *, timeout_s: float) -> dict | None: ...


def containment_evidence(
    driver: ForeignCleanup, item: RecoveryItem, *, timeout_s: float
) -> dict[str, Any] | None:
    """Concrete evidence that the recorded boundary is gone, or None (quarantine).

    An attempt with no recorded boundary may have spawned a child just before the crash,
    so it is unverifiable rather than assumed empty.
    """
    if item.execution_boundary is None:
        return None
    try:
        identity = BoundaryIdentity.from_json(item.execution_boundary)
    except (KeyError, TypeError, ValueError):
        return None
    return driver.cleanup_foreign(identity, timeout_s=timeout_s)
