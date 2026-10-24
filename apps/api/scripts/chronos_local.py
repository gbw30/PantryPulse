"""Standalone real-model exercise; not the PantryPulse forecast service or API."""

import argparse
import csv
import hashlib
import json
import math
import os
import re
import statistics
import time
from datetime import UTC, date, datetime, timedelta
from importlib.metadata import version
from pathlib import Path

MODEL_ID = "amazon/chronos-2"
CUTOFF = date(2026, 10, 24)
HISTORY_DAYS = 90
HORIZON_DAYS = 7
QUANTILES = ("0.1", "0.5", "0.9")


def synthetic_history():
    """Six beneficiaries/two categories plus two hubs' donation series."""
    rows = []
    definitions = [
        ("DEMAND", f"beneficiary_{i}", category, i)
        for i in range(1, 7)
        for category in ("meals", "water")
    ] + [
        ("DONATION", f"hub_{i}", category, i)
        for i in range(1, 3)
        for category in ("meals", "water")
    ]
    for target_type, site, category, index in definitions:
        for step in range(HISTORY_DAYS):
            day = CUTOFF - timedelta(days=HISTORY_DAYS - step - 1)
            base = 35 + 7 * index + (15 if category == "water" else 0)
            seasonal = 6 * math.sin(2 * math.pi * day.weekday() / 7)
            rows.append(
                {
                    "item_id": f"{target_type}:{site}:{category}",
                    "timestamp": day.isoformat(),
                    "target": round(base + seasonal + 0.08 * step, 4),
                }
            )
    return rows


def input_hash(rows):
    payload = json.dumps(rows, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def read_pin(path):
    pin = json.loads(path.read_text(encoding="utf-8"))
    if pin.get("model_id") != MODEL_ID or not re.fullmatch(
        r"[0-9a-f]{40}", pin.get("revision", "")
    ):
        raise ValueError("Invalid model pin; expected amazon/chronos-2 and a full SHA.")
    return pin


def validate_predictions(records, series_ids):
    """Validate real output identity/dates/quantiles without modifying predictions."""
    expected = {
        (item, (CUTOFF + timedelta(days=offset)).isoformat())
        for item in series_ids
        for offset in range(1, HORIZON_DAYS + 1)
    }
    seen = set()
    negative = False
    for row in records:
        identity = (row["item_id"], str(row["timestamp"])[:10])
        if identity not in expected or identity in seen:
            raise ValueError("Unexpected or duplicate forecast series/date.")
        seen.add(identity)
        values = [float(row[key]) for key in QUANTILES]
        if not all(math.isfinite(value) for value in values):
            raise ValueError("Forecast has non-finite quantiles.")
        if values != sorted(values):
            raise ValueError("Forecast quantiles are not ordered.")
        negative = negative or values[0] < 0
    if seen != expected:
        raise ValueError("Forecast is missing required series/dates.")
    return ["Raw negative quantiles require a reviewed domain policy."] if negative else []


def write_csv(path, records):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)


def prepare(pin_path):
    from huggingface_hub import HfApi, snapshot_download

    if pin_path.exists():
        pin = read_pin(pin_path)
        print("Reusing the existing checkpoint pin; not following a moving main branch.")
    else:
        revision = HfApi().model_info(MODEL_ID).sha
        if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
            raise ValueError("Hub did not return a full checkpoint commit SHA.")
        pin = {"model_id": MODEL_ID, "revision": revision}
    snapshot_download(repo_id=MODEL_ID, revision=pin["revision"])
    pin_path.parent.mkdir(parents=True, exist_ok=True)
    pin_path.write_text(json.dumps(pin, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(pin, indent=2))
    print("Download complete. Copy this revision into the release record.")


def status(pin_path):
    for package in ("chronos-forecasting", "torch", "transformers"):
        print(f"{package}: {version(package)}")
    if pin_path.exists():
        print(json.dumps(read_pin(pin_path), indent=2))
    else:
        print("No checkpoint pin yet. Run prepare first.")


def run_model(args, pin_path, output):
    if not pin_path.exists():
        raise ValueError("No prepared model. Run the prepare command while online first.")
    pin = read_pin(pin_path)
    # All prediction commands use only downloaded files, even when internet is available.
    os.environ["HF_HUB_OFFLINE"] = "1"
    import resource

    import pandas as pd
    import torch
    from chronos import Chronos2Pipeline
    from huggingface_hub import snapshot_download

    torch.set_num_threads(args.threads)
    torch.set_num_interop_threads(1)
    local_path = snapshot_download(
        repo_id=MODEL_ID, revision=pin["revision"], local_files_only=True
    )
    started = time.perf_counter()
    pipeline = Chronos2Pipeline.from_pretrained(
        local_path, device_map="cpu", torch_dtype=torch.float32
    )
    pipeline.model.eval()
    load_seconds = time.perf_counter() - started
    print(f"Model loaded on CPU in {load_seconds:.2f}s; one resident instance.")
    output.mkdir(parents=True, exist_ok=True)
    rows = synthetic_history()
    frame = pd.DataFrame(rows)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"])
    series_ids = set(frame["item_id"])
    write_csv(output / "synthetic-history.csv", rows)

    def forecast():
        start = time.perf_counter()
        result = pipeline.predict_df(
            frame,
            prediction_length=HORIZON_DAYS,
            quantile_levels=[0.1, 0.5, 0.9],
            batch_size=args.batch_size,
            context_length=128,  # Retains all 90 provided observations.
            cross_learning=False,  # Explicit independent-series exercise.
            freq="D",
        )
        seconds = time.perf_counter() - start
        records = result.to_dict(orient="records")
        warnings = validate_predictions(records, series_ids)
        for row in records:
            row["timestamp"] = str(row["timestamp"])[:10]
            row["target_type"], row["site"], row["category"] = row["item_id"].split(":")
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        write_csv(output / f"forecast-{stamp}.csv", records)
        metadata = {
            **pin,
            "scope": "standalone synthetic model exercise, not integrated demo",
            "data_source": "SIMULATED",
            "input_sha256": input_hash(rows),
            "cutoff": CUTOFF.isoformat(),
            "horizon_days": HORIZON_DAYS,
            "history_days": HISTORY_DAYS,
            "series_count": len(series_ids),
            "prediction_rows": len(records),
            "threads": args.threads,
            "batch_size": args.batch_size,
            "cross_learning": False,
            "context_length": 128,
            "device": "cpu",
            "precision": "float32",
            "cache_hit": False,
            "model_load_seconds": load_seconds,
            "prediction_seconds": seconds,
            "process_high_water_rss_mib_cumulative": (
                resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
            ),
            "packages": {
                key: version(key) for key in ("chronos-forecasting", "torch", "transformers")
            },
            "warnings": warnings,
            "quantiles": "raw model quantiles, not calibrated intervals",
            "median_column": "0.5",
        }
        (output / f"forecast-{stamp}.json").write_text(
            json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
        )
        print(f"REAL INFERENCE: {len(records)} rows in {seconds:.2f}s. Output: /output")
        for warning in warnings:
            print(f"WARNING: {warning}")
        return seconds

    def benchmark():
        print("One warm-up forecast followed by measured repeats; same model instance.")
        forecast()
        timings = [forecast() for _ in range(args.repeats)]
        summary = {
            "repeats": len(timings),
            "median_seconds": statistics.median(timings),
            "maximum_seconds": max(timings),
            "threads": args.threads,
            "batch_size": args.batch_size,
            "note": "Synthetic model benchmark only; not application or accuracy validation.",
        }
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
        (output / f"benchmark-{stamp}.json").write_text(
            json.dumps(summary, indent=2) + "\n", encoding="utf-8"
        )
        print(json.dumps(summary, indent=2))

    if args.command == "smoke":
        forecast()
    elif args.command == "benchmark":
        benchmark()
    else:
        print("Commands: forecast (real inference), benchmark, quit. Model stays loaded.")
        while True:
            try:
                command = input("chronos> ").strip().lower()
            except EOFError:
                break
            if command in ("quit", "exit"):
                break
            if command == "forecast":
                forecast()
            elif command == "benchmark":
                benchmark()
            elif command:
                print("Choose forecast, benchmark or quit.")
    print("Session finished. Process memory will be released; model disk cache is retained.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "status", "session", "smoke", "benchmark"))
    parser.add_argument("--threads", type=int, choices=(1, 2, 4, 6), default=4)
    parser.add_argument("--batch-size", type=int, choices=(1, 4, 8, 16), default=16)
    parser.add_argument("--repeats", type=int, choices=range(1, 21), default=10)
    args = parser.parse_args()
    pin_path = Path(os.environ.get("CHRONOS_PIN_FILE", "/cache/model-pin.json"))
    output = Path(os.environ.get("CHRONOS_OUTPUT_DIR", "/output"))
    try:
        if args.command == "prepare":
            prepare(pin_path)
        elif args.command == "status":
            status(pin_path)
        else:
            run_model(args, pin_path, output)
    except KeyboardInterrupt:
        print("\nInterrupted. Disk cache retained; current run may have no completed output.")
        raise SystemExit(130) from None
    except Exception as error:
        raise SystemExit(f"FAILED ({type(error).__name__}): {error}") from error


if __name__ == "__main__":
    main()
