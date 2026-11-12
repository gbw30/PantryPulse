# covers: V1-A09
"""bench_import.py times the import.v1 step, prepare and publish (the part under the queue
lock) on a generated network, with peak RSS (W1-D05 step 3). Small here; 4,455,000 rows by
hand."""

import importlib.util
import json
from pathlib import Path

import pytest

from tests.integration.wq_support import API_ROOT, database_url

pytestmark = pytest.mark.integration


def _bench():
    spec = importlib.util.spec_from_file_location(
        "bench_import", API_ROOT / "scripts" / "bench_import.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_small_bench_writes_phase_seconds_and_peak_rss(tmp_path):
    database_url()  # NOT RUN (reported as skipped) without the test database
    out = tmp_path / "import.json"
    _bench().main(["--rows", "9000", "--batches", "500", "--schema", "w1_data_bench_test",
                   "--out", str(out)])
    report = json.loads(out.read_text())
    assert report["generated"] == {"locations": 100, "products": 500, "batches": 500,
                                   "demand_history": 9000}
    assert report["loaded"] == {"net_batches": 500, "net_demand_history": 9000}
    assert set(report["seconds"]) == {"generate", "step", "prepare", "publish", "total"}
    assert all(s > 0 for s in report["seconds"].values())
    assert report["peak_rss_bytes"] > 0


@pytest.mark.parametrize("given", [True, False], ids=["out-given", "default-out"])
def test_arguments_parse_when_the_script_sits_at_app_scripts(monkeypatch, tmp_path, capsys, given):
    bench = _bench()
    monkeypatch.setattr(bench, "API_ROOT", Path("/app"))  # the API image; /app has no grandparent
    out = ["--out", str(tmp_path / "import.json")] if given else []
    with pytest.raises(SystemExit) as stop:  # --rows 0 stops at the envelope check, before any DB
        bench.main([*out, "--rows", "0"])
    assert stop.value.code == 2
    assert "--rows must be 1..4,455,000" in capsys.readouterr().err


def test_rows_stop_at_what_the_generator_can_write(capsys):
    """One hub, which has no demand history (W5-D02, CR-w5-data-1): 99 pantries × 500 × 90."""
    bench = _bench()
    assert bench.MAX_ROWS == 4_455_000 == 99 * 500 * 90
    with pytest.raises(SystemExit) as stop:
        bench.main(["--rows", "4455001"])
    assert stop.value.code == 2 and "--rows must be 1..4,455,000" in capsys.readouterr().err
    lines = list(bench._rows("locations", 0, 0))
    assert [line.split(",")[2] for line in lines].count("hub") == 1
    first = 500 * 90 + 1  # all of L001 (the first pantry), then one row of L002
    assert {row.split(",")[0] for row in bench._rows("demand_history", first, 0)} == {
        "L001", "L002"}
