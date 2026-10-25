"""Keep compact review evidence in source; retain the complete report under artifacts."""

import argparse
import hashlib
import json
from pathlib import Path


def summarize(report):
    if (
        report["schema_version"] != "or-qualification-v1"
        or report["source_kind"] != "SIMULATED"
    ):
        raise ValueError("Expected an OR SIMULATED qualification report")
    result = {k: v for k, v in report.items() if k != "cases"}
    result["detail"] = (
        "Compact evidence; full exact goal metrics retained in checksummed local artifact"
    )
    result["cases"] = []
    for case in report["cases"]:
        row = {k: v for k, v in case.items() if k != "methods"}
        row["methods"] = []
        for method in case["methods"]:
            metrics = method["metrics"]
            item = {
                k: v
                for k, v in method.items()
                if k not in {"metrics", "decision_ids", "warnings"}
            }
            item["components"] = {
                k: v for k, v in metrics.items() if k not in {"goals", "warnings"}
            }
            item["goal_vectors"] = []
            for product in sorted({goal["product_id"] for goal in metrics["goals"]}):
                goals = sorted(
                    (g for g in metrics["goals"] if g["product_id"] == product),
                    key=lambda g: g["site_id"],
                )
                item["goal_vectors"].append(
                    {
                        "product_id": product,
                        **{
                            key: [g[key] for g in goals]
                            for key in (
                                "site_id",
                                "target",
                                "fulfilled",
                                "q",
                                "q0",
                                "ap",
                                "rp",
                            )
                        },
                    }
                )
            row["methods"].append(item)
        result["cases"].append(row)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    payload = args.input.read_bytes()
    result = summarize(json.loads(payload))
    result["full_report"] = {
        "path": str(args.input),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
