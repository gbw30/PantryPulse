"""OR ownership constrains its imports, not other developers' files."""

import ast
from pathlib import Path

FORBIDDEN = (
    "app.workers",
    "app.models",
    "app.repositories",
    "app.routers",
    "app.services.jobs",
    "app.services.or_",
    "app.schemas.or_http",
    "app.schemas.or_execution",
    "fastapi",
    "sqlalchemy",
    "alembic",
)
# W0-08a froze the router-facing v1 adapter here with a runtime argument: it reads the v1
# scenario and comparison tables. Only it may; no OR module may import it (w1-solver, lead review).
ADAPTER = "api_v3.py"


def test_or_modules_have_no_application_integration_dependencies():
    root = Path(__file__).resolve().parents[2]
    paths = [
        *(root / "app/services/optimization").glob("*.py"),
        root / "app/schemas/or_inputs.py",
        root / "app/schemas/or_outputs.py",
    ]
    violations = []
    for path in paths:
        if path.name == ADAPTER:
            continue
        for node in ast.walk(ast.parse(path.read_text())):
            names = (
                [node.module or "", *(f"{node.module}.{item.name}" for item in node.names)]
                if isinstance(node, ast.ImportFrom)
                else [item.name for item in node.names]
                if isinstance(node, ast.Import)
                else []
            )
            for name in names:
                if name.startswith((*FORBIDDEN, "app.services.optimization.api_v3")):
                    violations.append(f"{path.name}:{node.lineno}:{name}")
    assert not violations, violations
