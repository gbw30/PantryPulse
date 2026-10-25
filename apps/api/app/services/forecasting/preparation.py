"""Revision-aware, provider-independent daily preparation; no stock writes/imputation."""

import hashlib
import json
from collections import defaultdict
from datetime import UTC, date, datetime, timedelta
from math import fsum

from .schemas import (
    CoverageRevision,
    DailyObservation,
    DemandRevision,
    Diagnostics,
    ForecastInput,
    ForecastPolicy,
    HistoricalSnapshot,
    HistoryBundle,
    PreparedSeries,
    ReceiptRevision,
    SeriesScope,
    SourceRevision,
    series_identity,
)


def _select[Revision: (DemandRevision, ReceiptRevision, CoverageRevision)](
    rows: tuple[Revision, ...],
    as_of: datetime,
) -> tuple[Revision, ...]:
    """Select one complete visible revision per logical fact within a named dataset."""
    visible: dict[str, Revision] = {}
    identities: set[tuple[str, int]] = set()
    revision_ids = set()
    for row in rows:
        source = row.source
        if source.recorded_at > as_of:
            continue
        identity = (source.logical_key, source.revision)
        if identity in identities or source.revision_id in revision_ids:
            raise ValueError(f"Duplicate revision for {source.logical_key}")
        identities.add(identity)
        revision_ids.add(source.revision_id)
        prior = visible.get(source.logical_key)
        if prior is None or source.revision > prior.source.revision:
            visible[source.logical_key] = row
    return tuple(visible[key] for key in sorted(visible))


def _source_order(source: SourceRevision) -> tuple[str, int, str]:
    return source.logical_key, source.revision, str(source.revision_id)


def canonical_hash(inputs: ForecastInput) -> str:
    """Canonical UTF-8 JSON v1: sorted keys, compact separators, ISO dates, no NaN.

    Scope, days, sources and receipt line IDs are sorted during preparation. Execution
    IDs/timestamps do not enter identity. snapshot_as_of is a knowledge cutoff, not
    an execution timestamp, and intentionally does enter identity.
    """
    payload = inputs.model_dump(mode="json", exclude={"input_hash"})
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _demand_days(
    rows: tuple[DemandRevision, ...], scope: SeriesScope, policy: ForecastPolicy, cutoff: date
) -> dict[date, DailyObservation]:
    days = {}
    for row in rows:
        if row.key != scope.key or row.day > cutoff:
            continue
        if row.day in days:
            raise ValueError(f"Duplicate demand day: {row.day}")
        value = row.requested_units
        basis = "REQUESTED" if value is not None else "UNAVAILABLE"
        flags = ()
        if value is None and row.fulfilled_units is not None:
            if policy.allow_fulfilled_proxy:
                value, basis, flags = row.fulfilled_units, "FULFILLED_PROXY", ("FULFILLED_PROXY",)
            else:
                flags = ("PROXY_NOT_AUTHORIZED",)
        days[row.day] = DailyObservation(
            day=row.day,
            value=value,
            is_missing=value is None,
            target_basis=basis,
            source_classifications=(row.source_classification,),
            sources=(row.source,),
            requested_units=row.requested_units,
            fulfilled_units=row.fulfilled_units,
            unmet_units=row.unmet_units,
            quality_flags=flags,
        )
    return days


def _donation_days(
    receipts: tuple[ReceiptRevision, ...],
    coverage: tuple[CoverageRevision, ...],
    scope: SeriesScope,
    cutoff: date,
) -> dict[date, DailyObservation]:
    totals: dict[date, list[float]] = defaultdict(list)
    sources: dict[date, list[SourceRevision]] = defaultdict(list)
    line_ids: dict[date, list] = defaultdict(list)
    classifications: dict[date, set] = defaultdict(set)
    for receipt in receipts:
        if receipt.receiving_site_id != scope.key.site_id or receipt.local_day > cutoff:
            continue
        for line in receipt.lines:
            if line.product_id != scope.key.product_id:
                continue
            if receipt.timezone != scope.timezone or line.unit != scope.unit:
                raise ValueError("Receipt timezone/unit differs from selected series")
            day = receipt.local_day
            totals[day].append(line.received_units)
            if receipt.source not in sources[day]:
                sources[day].append(receipt.source)
            line_ids[day].append(line.line_id)
            classifications[day].add(receipt.source_classification)
    declarations = {}
    for row in coverage:
        if row.key == scope.key and row.day <= cutoff:
            if row.day in declarations:
                raise ValueError(f"Duplicate reporting coverage day: {row.day}")
            declarations[row.day] = row
    days = {}
    for day in sorted(totals.keys() | declarations.keys()):
        declaration = declarations.get(day)
        complete = declaration is not None and declaration.complete
        if declaration:
            sources[day].append(declaration.source)
            classifications[day].add(declaration.source_classification)
        value = fsum(totals[day]) if day in totals or complete else None
        days[day] = DailyObservation(
            day=day,
            value=value,
            is_missing=value is None,
            target_basis="RECEIVED" if value is not None else "UNAVAILABLE",
            sources=tuple(sorted(sources[day], key=_source_order)),
            receipt_line_ids=tuple(sorted(line_ids[day], key=str)),
            source_classifications=tuple(sorted(classifications[day])),
            quality_flags=() if complete else ("INCOMPLETE_RECEIPT_COVERAGE",),
        )
    return days


def prepare(
    history: HistoryBundle,
    *,
    data_cutoff_date: date,
    snapshot_as_of: datetime,
    policy: ForecastPolicy,
) -> ForecastInput:
    # Revalidate even model_copy/model_construct callers before any provider runs.
    history = HistoryBundle.model_validate(history.model_dump())
    policy = ForecastPolicy.model_validate(policy.model_dump())
    if snapshot_as_of.tzinfo is None or snapshot_as_of.utcoffset() is None:
        raise ValueError("snapshot_as_of requires an explicit timezone")
    snapshot_as_of = snapshot_as_of.astimezone(UTC)
    demand = _select(history.demand, snapshot_as_of)
    receipts = _select(history.receipts, snapshot_as_of)
    coverage = _select(history.coverage, snapshot_as_of)
    keys = {scope.key for scope in history.scope}
    demand = tuple(row for row in demand if row.key in keys and row.day <= data_cutoff_date)
    coverage = tuple(row for row in coverage if row.key in keys and row.day <= data_cutoff_date)
    receipts = tuple(
        row.model_copy(
            update={
                "lines": tuple(sorted(row.lines, key=lambda line: str(line.line_id))),
            }
        )
        for row in receipts
        if row.local_day <= data_cutoff_date
        and any(
            scope.key.target_type == "DONATION"
            and scope.key.site_id == row.receiving_site_id
            and any(line.product_id == scope.key.product_id for line in row.lines)
            for scope in history.scope
        )
    )
    prepared = []
    for scope in sorted(history.scope, key=lambda s: series_identity(s.key)):
        days = (
            _demand_days(demand, scope, policy, data_cutoff_date)
            if scope.key.target_type == "DEMAND"
            else _donation_days(receipts, coverage, scope, data_cutoff_date)
        )
        start = min(days, default=data_cutoff_date - timedelta(days=policy.sparse_window_days - 1))
        observations = []
        for offset in range((data_cutoff_date - start).days + 1):
            day = start + timedelta(days=offset)
            observations.append(
                days.get(
                    day,
                    DailyObservation(
                        day=day,
                        value=None,
                        is_missing=True,
                        target_basis="UNAVAILABLE",
                    ),
                )
            )
        valid = [row for row in observations if not row.is_missing]
        bases = {row.target_basis for row in valid}
        if len(bases) > 1 and not policy.allow_mixed_proxy_history:
            raise ValueError("Mixed proxy/requested history requires explicit policy opt-in")
        basis = next(iter(bases)) if len(bases) == 1 else "MIXED" if bases else "UNAVAILABLE"
        warnings = {flag for row in observations for flag in row.quality_flags}
        if any("SIMULATED" in row.source_classifications for row in observations):
            warnings.add("SIMULATED_SOURCE")
        if len(valid) < len(observations):
            warnings.add("HISTORY_GAPS")
        if history.availability_semantics == "RETROSPECTIVE_CORRECTED":
            warnings.add("RETROSPECTIVE_CORRECTED_HISTORY")
        diagnostics = Diagnostics(
            observed_count=len(valid),
            missing_count=len(observations) - len(valid),
            proxy_fraction=(
                sum(row.target_basis == "FULFILLED_PROXY" for row in valid) / len(valid)
                if valid
                else 0
            ),
            reference_weekday_count=sum(
                row.day >= data_cutoff_date - timedelta(days=6) for row in valid
            ),
            trailing_sample_count=sum(
                row.day > data_cutoff_date - timedelta(days=policy.sparse_window_days)
                for row in valid
            ),
        )
        prepared.append(
            PreparedSeries(
                scope=scope,
                observations=tuple(observations),
                diagnostics=diagnostics,
                target_basis=basis,
                warnings=tuple(sorted(warnings)),
            )
        )
    inputs = ForecastInput(
        organization_id=history.organization_id,
        dataset_id=history.dataset_id,
        data_cutoff_date=data_cutoff_date,
        snapshot_as_of=snapshot_as_of,
        availability_semantics=history.availability_semantics,
        policy=policy,
        source_snapshot=HistoricalSnapshot(demand=demand, receipts=receipts, coverage=coverage),
        series=tuple(prepared),
        input_hash="",
    )
    return inputs.model_copy(update={"input_hash": canonical_hash(inputs)})


def validate_input(inputs: ForecastInput) -> ForecastInput:
    """Revalidate saved/constructed inputs against both their hash and exact raw facts."""
    inputs = ForecastInput.model_validate(inputs.model_dump())
    if inputs.input_hash != canonical_hash(inputs):
        raise ValueError("Forecast input hash does not match frozen content")
    reconstructed = prepare(
        HistoryBundle(
            organization_id=inputs.organization_id,
            dataset_id=inputs.dataset_id,
            scope=tuple(series.scope for series in inputs.series),
            demand=inputs.source_snapshot.demand,
            receipts=inputs.source_snapshot.receipts,
            coverage=inputs.source_snapshot.coverage,
            availability_semantics=inputs.availability_semantics,
        ),
        data_cutoff_date=inputs.data_cutoff_date,
        snapshot_as_of=inputs.snapshot_as_of,
        policy=inputs.policy,
    )
    if reconstructed != inputs:
        raise ValueError(
            "Forecast input contradicts canonical preparation of selected source facts"
        )
    return inputs
