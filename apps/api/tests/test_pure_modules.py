"""READY helpers (BACKEND-SPEC.md section 13) import no solver, model or database packages."""

import subprocess
import sys
from pathlib import Path

import pytest

API_ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = ("ortools", "sqlalchemy", "chronos", "torch", "psycopg")


@pytest.mark.parametrize(
    "module",
    [
        "app.schemas.planning_primitives",
        "app.services.transfer_modes",
        "app.services.demand_targets",
        "app.services.fixed_point",
        "app.services.solver_outcomes",
        "app.services.forecasting.history",
    ],
)
def test_module_imports_no_solver_model_or_database_packages(module):
    # A fresh interpreter, because other tests may already have imported these packages.
    code = (
        f"import sys, {module}; "
        f"bad = [m for m in {FORBIDDEN!r} if m in sys.modules]; "
        "print(bad); sys.exit(1 if bad else 0)"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=API_ROOT, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr
