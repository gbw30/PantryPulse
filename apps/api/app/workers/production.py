"""Production allowlist, shared by API admission and controlled worker children."""

from app.services.jobs.registry import Registry
from app.workers.allocation import REGISTRATION as ALLOCATION_REGISTRATION
from app.workers.chronos_forecasting import REGISTRATION as CHRONOS_REGISTRATION
from app.workers.forecasting import REGISTRATION
from app.workers.optimization import REGISTRATION as OR_REGISTRATION

REGISTRY = Registry([REGISTRATION, CHRONOS_REGISTRATION, OR_REGISTRATION, ALLOCATION_REGISTRATION])
