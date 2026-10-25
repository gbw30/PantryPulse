"""Production allowlist, shared by API admission and controlled worker children."""

from app.services.jobs.registry import Registry
from app.workers.forecasting import REGISTRATION
from app.workers.or_handler import registrations

REGISTRY = Registry([REGISTRATION, *registrations()])
