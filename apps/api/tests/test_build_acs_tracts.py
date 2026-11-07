# covers: V1-A08
"""The ACS tract builder keeps tracts only, marks unknowns empty and is byte-reproducible."""

import csv
import gzip
import importlib.util
import io
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "build_acs_tracts", Path(__file__).resolve().parents[1] / "scripts/build_acs_tracts.py"
)
assert spec and spec.loader
acs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(acs)

POVERTY = [
    "GEO_ID|B17001_E001|B17001_M001|B17001_E002|B17001_M002\n",
    "0400000US12|21000000|100|2700000|50\n",  # a state: dropped
    "1400000US12001000201|1781|386|310|129\n",
    "1400000US12001000202|0|13|0|13\n",  # zero universe stays 0; the rate is unknown downstream
    "1400000US12001000203||13|-666666666|13\n",  # blank and sentinel become unknown
]
SNAP = [
    "GEO_ID|B22003_E001|B22003_M001|B22003_E002|B22003_M002\n",
    "1400000US12001000201|736|137|100|72\n",
    "1400000US12001000204|50|9|5|3\n",  # only in the SNAP table
]


def test_tract_rows_with_unknowns_are_empty():
    poverty = acs.read_tracts(iter(POVERTY), acs.TABLES["B17001"])
    snap = acs.read_tracts(iter(SNAP), acs.TABLES["B22003"])
    data = acs.build(poverty, snap)
    rows = list(csv.reader(io.StringIO(gzip.decompress(data).decode())))
    assert rows == [
        list(acs.COLUMNS),
        ["12001000201", "1781", "310", "736", "100"],
        ["12001000202", "0", "0", "", ""],
        ["12001000203", "", "", "", ""],
        ["12001000204", "", "", "50", "5"],
    ]
    assert acs.build(poverty, snap) == data  # reproducible bytes
