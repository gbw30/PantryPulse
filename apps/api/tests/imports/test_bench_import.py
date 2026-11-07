# covers: V1-A09
"""bench_import.py times the import.v1 step, prepare and publish (the part under the queue
lock) on a generated network, with peak RSS (W1-D05 step 3). Small here; 4.5 M rows by hand."""

import importlib.util
import json

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
