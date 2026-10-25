"""Real module-mode CLI input, exit-code, containment and verification contracts."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

API = Path(__file__).resolve().parents[2]
SNAPSHOT = API.parents[1] / "data/demo/or-v2/six-beneficiary-v2.snapshot.json"


def invoke(module, *args, env=None):
    return subprocess.run(
        [sys.executable, "-m", f"scripts.{module}", *map(str, args)],
        cwd=API,
        capture_output=True,
        text=True,
        timeout=75,
        env=os.environ.copy() if env is None else env,
    )


@pytest.mark.parametrize("data", [None, [], 7, True, {"schema_version": "unknown"}, "{"])
def test_validator_reports_bad_json_shapes_as_invalid_input(tmp_path, data):
    source, report = tmp_path / "input.json", tmp_path / "report.json"
    source.write_text(data if isinstance(data, str) else json.dumps(data))
    result = invoke("or_validate_input", "--input", source, "--report", report)
    assert result.returncode == 2, result.stderr
    assert json.loads(report.read_text())["valid"] is False
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize("suffix", ["input", "snapshot"])
def test_validator_accepts_real_exact_fixture(tmp_path, suffix):
    source = SNAPSHOT.with_name(f"six-beneficiary-v2.{suffix}.json")
    report = tmp_path / "validation.json"
    result = invoke("or_validate_input", "--input", source, "--report", report)
    assert result.returncode == 0, result.stderr
    assert json.loads(report.read_text())["valid"]


def test_single_method_cli_preserves_a_verified_zero_transfer_plan(tmp_path):
    output = tmp_path / "zero-plan.json"
    result = invoke(
        "or_solve",
        "--snapshot",
        SNAPSHOT.with_name("zero-stock-v2.snapshot.json"),
        "--method",
        "CLASSICAL_GP",
        "--output",
        output,
    )
    assert result.returncode == 0, result.stderr
    saved = json.loads(output.read_text())
    assert saved["execution"] == "OFFLINE"
    assert saved["result"]["outcome"] == "VERIFIED"
    assert saved["result"]["candidate"]["assignments"] == []


@pytest.fixture(scope="module")
def pair(tmp_path_factory):
    folder = tmp_path_factory.mktemp("bounded-or-cli")
    output = folder / "pair.json"
    result = invoke("or_compare", "--snapshot", SNAPSHOT, "--output", output)
    assert result.returncode == 0, result.stderr
    return folder, json.loads(output.read_text())


def test_real_offline_pair_has_verified_exact_objectives_and_shared_model(pair):
    _, saved = pair
    assert saved["execution"] == "OFFLINE"
    comparison = saved["comparison"]
    assert comparison["outcome"] == "SUCCEEDED"
    first, second = comparison["methods"]
    assert first["objective"] == {"numerator": 163, "denominator": 50}
    assert second["objective"] == {"numerator": 1393, "denominator": 300}
    assert first["physical_fingerprint"] == second["physical_fingerprint"]
    assert all(method["verification"]["passed"] for method in (first, second))


def test_cli_independent_verification_accepts_real_candidate_and_rejects_tamper(pair):
    folder, saved = pair
    candidate = saved["comparison"]["methods"][0]["candidate"]
    path, report = folder / "candidate.json", folder / "verification.json"
    path.write_text(json.dumps(candidate))
    result = invoke("or_verify", "--snapshot", SNAPSHOT, "--candidate", path, "--report", report)
    assert result.returncode == 0, result.stderr
    assert json.loads(report.read_text())["passed"]
    candidate["assignments"][0]["units"] += 1
    path.write_text(json.dumps(candidate))
    result = invoke("or_verify", "--snapshot", SNAPSHOT, "--candidate", path, "--report", report)
    assert result.returncode == 3, result.stderr
    assert json.loads(report.read_text())["passed"] is False


@pytest.mark.parametrize("status", ["INFEASIBLE", "UNKNOWN", "MODEL_INVALID"])
def test_native_extractor_never_reads_a_forbidden_vector(status):
    from app.services.optimization.extract import read_candidate

    class ForbiddenRead:
        def value(self, _variable):
            raise AssertionError("Forbidden native vector access")

    assert read_candidate(status, ForbiddenRead(), None) is None
