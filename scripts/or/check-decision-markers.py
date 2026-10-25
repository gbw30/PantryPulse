"""Check draft decisions against real behavior, assertion-bearing tests and fixtures."""
import ast
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IDS = {f"OR-DEC-{number:03d}" for number in range(1, 21)}


def markers(text):
    result = set()
    for match in re.finditer(r"OR-DEC-(\d{3})((?:/\d{3})*)", text):
        result.add(f"OR-DEC-{match[1]}")
        result.update(f"OR-DEC-{number}" for number in match[2].split("/") if number)
    return result


def symbol(path, name):
    source = (ROOT / path).read_text()
    nodes = [node for node in ast.walk(ast.parse(source))
             if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
             and node.name == name]
    if not nodes:
        raise ValueError(f"Missing implementation/test symbol: {path}:{name}")
    return source, nodes


def main():
    registry = (ROOT / "docs/optimization/DECISION-REGISTER.md").read_text()
    manifest = json.loads((ROOT / "docs/optimization/decision-manifest.json").read_text())
    if set(manifest["decisions"]) != IDS:
        raise ValueError("Manifest must cover exactly OR-DEC-001 through OR-DEC-020")
    external = []
    for decision, entry in manifest["decisions"].items():
        section = registry.split(f"## {decision}\n", 1)[1].split("\n## ", 1)[0]
        if entry.get("ownership") in {"EXTERNAL_OWNER", "WITHDRAWN"}:
            expected = {"OR-DEC-012": "DEFERRED_EXTERNAL_OWNER",
                        "OR-DEC-014": "WITHDRAWN_BY_USER_SCOPE_CORRECTION"}
            if entry.get("status") != expected.get(decision) or entry["status"] not in section:
                raise ValueError(f"Unverified external/withdrawn status: {decision}")
            if not entry.get("reason") or not (ROOT / entry["handoff"]).is_file():
                raise ValueError(f"Missing external handoff: {decision}")
            if "behavior" in entry or "tests" in entry:
                raise ValueError(f"External ownership cannot claim core implementation: {decision}")
            external.append(decision)
            continue
        if "SELECTED_FOR_DRAFT_1" not in section:
            raise ValueError(f"Decision status missing: {decision}")
        source, _ = symbol(entry["behavior"]["path"], entry["behavior"]["symbol"])
        if decision not in markers(source) or "[PROVISIONAL]" not in source:
            raise ValueError(f"Provisional behavior marker missing: {decision}")
        if not entry["tests"]:
            raise ValueError(f"Behavioral tests missing: {decision}")
        for test in entry["tests"]:
            source, nodes = symbol(test["path"], test["symbol"])
            if decision not in markers(source):
                raise ValueError(f"Test decision marker missing: {decision}")
            if not any(isinstance(node, ast.Assert) or (
                isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == "raises") for item in nodes for node in ast.walk(item)):
                raise ValueError(f"Test contains no assertions: {test}")
    for path in (ROOT / "apps/api/app").rglob("*.py"):
        unknown = markers(path.read_text()) - IDS
        if unknown:
            raise ValueError(f"Unregistered behavior markers in {path}: {sorted(unknown)}")
    for name in manifest["fixtures"]:
        data = json.loads((ROOT / name).read_text())
        if set(data["decision_ids"]) != IDS or set(data["policy"]["decision_ids"]) != IDS:
            raise ValueError(f"Incomplete scenario/policy decision metadata: {name}")
        if not data["transfer_mode"] or data["package"]["source_kind"] != "SIMULATED":
            raise ValueError(f"Fixture mode/provenance missing: {name}")
    print(f"{len(IDS)-len(external)} core decisions checked; "
          f"{len(external)} external/withdrawn decisions explicitly reported. All fixture IDs retained.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
