"""Production allowlist, shared by API admission and controlled worker children."""

from app.services.jobs.registry import Registry
from app.workers.forecasting import REGISTRATION
from app.workers.optimization import REGISTRATION as OR_REGISTRATION

REGISTRY = Registry([REGISTRATION, OR_REGISTRATION])
