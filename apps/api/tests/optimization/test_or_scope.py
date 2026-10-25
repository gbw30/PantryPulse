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


def test_or_modules_have_no_application_integration_dependencies():
    root = Path(__file__).resolve().parents[2]
    paths = [
        *(root / "app/services/optimization").glob("*.py"),
        root / "app/schemas/or_inputs.py",
        root / "app/schemas/or_outputs.py",
    ]
    violations = []
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text())):
            names = (
                [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else [item.name for item in node.names]
                if isinstance(node, ast.Import)
                else []
            )
            for name in names:
                if name.startswith(FORBIDDEN):
                    violations.append(f"{path.name}:{node.lineno}:{name}")
    assert not violations, violations
