"""Deployment shutdown must accommodate the accepted longest worker operation."""

from pathlib import Path

import yaml

from app.services.jobs.contracts import PRODUCTION_PROFILE

ROOT = Path(__file__).resolve().parents[3]


def test_compute_worker_stop_grace_covers_maximum_drain_and_cleanup():
    config = yaml.safe_load((ROOT / "compose.compute.yaml").read_text())
    grace_seconds = int(config["services"]["worker"]["stop_grace_period"].removesuffix("s"))
    maximum_operation = max(
        PRODUCTION_PROFILE.forecast_total_s,
        PRODUCTION_PROFILE.allocation_total_s,
        PRODUCTION_PROFILE.comparison_total_s,
    )
    # Supervisor drain has 30 seconds of reconciliation margin; allow another
    # five seconds before Docker's forced shutdown can interrupt that cleanup.
    assert grace_seconds >= maximum_operation + 35
