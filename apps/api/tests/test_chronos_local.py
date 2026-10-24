"""Offline checks for the standalone runner's input/output safeguards, not model inference."""

import json
from datetime import timedelta

import pytest

from scripts.chronos_local import (
    CUTOFF,
    HORIZON_DAYS,
    MODEL_ID,
    input_hash,
    read_pin,
    synthetic_history,
    validate_predictions,
)


def valid_output():
    return [
        {
            "item_id": "DEMAND:beneficiary_1:meals",
            "timestamp": (CUTOFF + timedelta(days=offset)).isoformat(),
            "0.1": 1.0,
            "0.5": 2.0,
            "0.9": 3.0,
        }
        for offset in range(1, HORIZON_DAYS + 1)
    ]


def test_history_keeps_target_identity_and_cutoff():
    rows = synthetic_history()
    ids = {row["item_id"] for row in rows}
    assert len(ids) == 16
    assert sum(item.startswith("DEMAND:") for item in ids) == 12
    assert sum(item.startswith("DONATION:") for item in ids) == 4
    for item in ids:
        dates = [row["timestamp"] for row in rows if row["item_id"] == item]
        assert len(dates) == len(set(dates)) == 90
        assert max(dates) == CUTOFF.isoformat()
    changed = [dict(row) for row in rows]
    changed[0]["target"] += 1
    assert input_hash(changed) != input_hash(rows)


@pytest.mark.parametrize("defect", ("duplicate", "missing", "wrong_date", "nan", "order"))
def test_rejects_invalid_forecasts(defect):
    rows = valid_output()
    if defect == "duplicate":
        rows.append(dict(rows[0]))
    elif defect == "missing":
        rows.pop()
    elif defect == "wrong_date":
        rows[0]["timestamp"] = CUTOFF.isoformat()
    elif defect == "nan":
        rows[0]["0.5"] = float("nan")
    else:
        rows[0]["0.1"] = 100
    with pytest.raises(ValueError):
        validate_predictions(rows, {"DEMAND:beneficiary_1:meals"})


def test_warns_without_silently_clipping_raw_quantiles():
    rows = valid_output()
    assert validate_predictions(rows, {"DEMAND:beneficiary_1:meals"}) == []
    rows[0]["0.1"] = -1.0
    assert validate_predictions(rows, {"DEMAND:beneficiary_1:meals"})
    assert rows[0]["0.1"] == -1.0


def test_model_pin_requires_exact_checkpoint(tmp_path):
    pin_path = tmp_path / "pin.json"
    pin_path.write_text(json.dumps({"model_id": MODEL_ID, "revision": "main"}))
    with pytest.raises(ValueError, match="full SHA"):
        read_pin(pin_path)
    pin_path.write_text(json.dumps({"model_id": MODEL_ID, "revision": "a" * 40}))
    assert read_pin(pin_path)["revision"] == "a" * 40
