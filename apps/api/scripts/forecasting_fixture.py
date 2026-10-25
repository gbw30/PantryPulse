"""Deterministically expand the checked-in fixture specification; no database writes."""

import json
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
from zoneinfo import ZoneInfo

from app.services.forecasting.evaluation import EvaluationOrigin
from app.services.forecasting.schemas import ForecastPolicy, HistoryBundle

SPEC_PATH = Path(__file__).resolve().parents[3] / "data/demo/forecasting-v1.json"


def build_fixture() -> tuple[HistoryBundle, ForecastPolicy, tuple[EvaluationOrigin, ...], datetime]:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    dataset = uuid5(NAMESPACE_URL, spec["dataset_name"])
    organization = uuid5(dataset, "organization")
    start = date.fromisoformat(spec["start_date"])
    zone = ZoneInfo(spec["timezone"])
    scope, demand, receipts, coverage = [], [], [], []

    def at(day, hour):
        return datetime.combine(day, time(hour), tzinfo=zone).astimezone(UTC)

    def source(name, day, revision=1, delay=0):
        return {
            "organization_id": organization,
            "dataset_id": dataset,
            "logical_key": name,
            "revision_id": uuid5(dataset, f"{name}:{revision}"),
            "revision": revision,
            "recorded_at": at(day + timedelta(days=delay), 23),
        }

    for site_index, site in enumerate(spec["sites"]):
        site_id = uuid5(dataset, site["name"])
        products = [
            (uuid5(dataset, product["name"]), product["unit"]) for product in spec["products"]
        ]
        for product_id, unit in products:
            for target in site["required_targets"]:
                scope.append(
                    {
                        "key": {
                            "organization_id": organization,
                            "site_id": site_id,
                            "product_id": product_id,
                            "target_type": target,
                        },
                        "unit": unit,
                        "timezone": spec["timezone"],
                        "required": True,
                    }
                )
        for index in range(spec["history_days"]):
            day = start + timedelta(days=index)
            for product_index, (product_id, _unit) in enumerate(products):
                identity = f"{site_index}:{product_index}:{day}"
                key = {
                    "organization_id": organization,
                    "site_id": site_id,
                    "product_id": product_id,
                }
                if site["role"] == "BENEFICIARY" and not (site_index == 0 and index == 23):
                    requested = (
                        20 + site_index * 3 + product_index * 8 + day.weekday() * 2 + index // 28
                    )
                    proxy = site_index == 0 and index == 24
                    demand.append(
                        {
                            "source": source(f"demand:{identity}", day),
                            "key": {**key, "target_type": "DEMAND"},
                            "day": day,
                            "requested_units": None if proxy else requested,
                            "fulfilled_units": requested - 2,
                            "unmet_units": None if proxy else 2,
                            "source_classification": "SIMULATED",
                        }
                    )
                if not (site_index == 0 and index == 32):
                    coverage.append(
                        {
                            "source": source(f"coverage:{identity}", day),
                            "key": {**key, "target_type": "DONATION"},
                            "day": day,
                            "complete": True,
                            "source_classification": "SIMULATED",
                        }
                    )
            if index % 7 in (0, 3) or index == 20:
                event_count = 2 if index == 20 else 1
                for event in range(event_count):
                    name = f"receipt:{site_index}:{day}:{event}"
                    for revision in (1, 2) if index == 14 and event == 0 else (1,):
                        receipts.append(
                            {
                                "source": source(
                                    name, day, revision, delay=2 if revision == 2 else 0
                                ),
                                "donor_id": uuid5(dataset, f"donor:{event}"),
                                "receiving_site_id": site_id,
                                "received_at": at(day, 12),
                                "local_day": day,
                                "timezone": spec["timezone"],
                                "source_classification": "SIMULATED",
                                "lines": [
                                    {
                                        "line_id": uuid5(
                                            dataset, f"{name}:{revision}:{product_id}"
                                        ),
                                        "product_id": product_id,
                                        "unit": unit,
                                        "received_units": 5
                                        + site_index
                                        + pindex * 3
                                        + (revision - 1),
                                    }
                                    for pindex, (product_id, unit) in enumerate(products)
                                ],
                            }
                        )
    history = HistoryBundle(
        organization_id=organization,
        dataset_id=dataset,
        scope=tuple(scope),
        demand=tuple(demand),
        receipts=tuple(receipts),
        coverage=tuple(coverage),
    )
    origins = tuple(
        EvaluationOrigin(
            data_cutoff_date=start + timedelta(days=offset),
            snapshot_as_of=at(start + timedelta(days=offset + 1), 0),
        )
        for offset in spec["evaluation_origin_offsets"]
    )
    return (
        history,
        ForecastPolicy(**spec["policy"]),
        origins,
        at(
            start + timedelta(days=spec["history_days"]),
            0,
        ),
    )
