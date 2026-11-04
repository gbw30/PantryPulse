# Spike S4: bulk import at 4.5 M rows (W0-03)

Status: partial. Stages (b) through (e) were measured. Stage (a), the FastAPI upload, was **not measured** because the turn budget ran out. Spike code is throwaway: `apps/api/spikes/s4/`.

## Setup

- Base `979b9cf`, branch `spike/w0-s4`. The commit that holds this report is the branch tip.
- Machine: WSL2 (kernel 6.18.54.1), 16 cores, 15 GiB RAM, Node v24.16.0. Python deps come from `uv sync --frozen` (psycopg 3.3.6 binary, python-multipart 0.0.32, FastAPI 0.162.0, Starlette 1.9.0, uvicorn 0.54.0).
- Database: `w0_s4_test` on `pp-ci-postgres`, PostgreSQL 16.15, all defaults: shared_buffers 128MB, work_mem 4MB, maintenance_work_mem 64MB, max_parallel_workers_per_gather 2, synchronous_commit on.
- Data: `gen.py`, seed 20261104. 100 locations × 500 products × 90 days (2026-08-06..2026-11-03, `as_of_date` 2026-11-03).
  - **4,500,000 rows, 143,097,619 bytes (143.1 MB)**, sha256 `018d6ec9…c393`.
  - 88,249 blank quantities (1.96%).
  - Generation took 4.5 s with a 14 MB peak.

## Commands (cwd `apps/api`)

```
uv sync --frozen --directory apps/api            # uv.lock unchanged
.venv/bin/python spikes/s4/gen.py spikes/s4/out
bash spikes/s4/run_stages.sh                     # (c)+(d)+(e), 5 variants; `planted` arg = planted check only
node --experimental-strip-types spikes/s4/proxy_probe.mjs "../web/src/app/api/v1/[...path]/route.ts" spikes/s4/out/demand_history.csv
```

Not run: `spikes/s4/run_upload.sh` (stage a: three uvicorn variants on 127.0.0.1:8031) and `spikes/s4/commit_variants.py` (faster commit shapes). Both were written but never executed, so they have no results.

## Measurement method

- Every step runs on a fresh connection.
- "PG peak" is that backend's `VmHWM`, read from `/proc` in the container. It includes shared buffers the backend touched. It **excludes parallel workers**.
- "Client peak" is the `/usr/bin/time` max RSS of the whole Python process.
- Times are wall seconds from one run each. The variance column is a second run where one exists.

## Results

| Stage | Seconds | Peak MB | Notes |
|---|---|---|---|
| (a) FastAPI multipart upload | not measured | not measured | Code-read only: `main.py:65-84` reads the **whole body into memory** before routing (limit 64 KB, or 512 KB for planning-assumptions). Any upload route must bypass `RequestBoundary` by path. |
| (b) Next proxy, 143 MB body | 0.064 to 413 | 85 node RSS | The real handler function was called outside Next. It read 131,072 bytes, then returned `413 INPUT_TOO_LARGE`. A non-allow-listed path returns 404 without reading the body. Code (`route.ts:73-90`) buffers the full body in memory, caps it at 64 KB and sets a 20 s `AbortSignal.timeout`. Next's own server wrapper was not exercised. |
| (c) COPY, Python `csv.reader` → `copy.write_row`, UNLOGGED | 5.51 / 6.10 (planted) | PG 35, client 38 | CSV-correct (quoted fields). Line numbers come from `reader.line_num`. 4.5 M rows. |
| (c) same, LOGGED staging | 6.13 | PG 37, client 38 | WAL cost is small here. |
| (c) raw-line COPY + SQL `string_to_array` split | 17.93 (copy 3.3 + split 14.7) | PG 112, client 158 | Slower and **not quote-aware**: valid line 71 (`"L001",…`) produced 4 false errors. Rejected. |
| (c) ANALYZE staging | 0.3–0.4 | 38 | |
| (d) malformed (field count, blank required, date, number, basis) | 5.49 / 5.50 | 116 | The first version took 38.4 s. Cause: a per-row `LATERAL (VALUES …)` over 4.5 M rows (EXPLAIN: 7 µs × 4.5 M loops). A single-pass prefilter fixed it. |
| (d) negative | 0.82–0.90 | 95 | |
| (d) fractional | 1.06 | 95 | |
| (d) duplicate (window over key) | 4.6–6.7 | 121 | External sort at work_mem 4MB. |
| (d) unknown ID (anti-join to locations/products) | 0.77–1.22 | 98 | |
| (d) over-envelope (row cap) + after `as_of_date` + > 90 days | 2.1–2.3 | 123 | |
| (d) missing expiry (inventory.csv, 1,000 rows) | 0.00 | 18 | The class does not apply to demand history. Its time was not measured at 4.5 M rows. |
| (d) report first 1,000 errors (ORDER BY line) | 0.00 | 17 | |
| **(d) total** | **≈ 17.5** | 123 | Sum of the classes, clean file, python mode. |
| (e) commit gate on planted file | 0.00 | 17 | 13 errors, nothing written. |
| (e) forced INSERT on planted staging, without the gate | 0.03 | 81 | Rolled back (`NotNullViolation`). Target rows after: 0. |
| (e) commit 4.5 M rows into a target with PK + 2 FKs, one transaction | **61.6 / 65.8** | **312** | The biggest cost. The target was 454 MB afterwards, with 90,033 NULL quantities preserved (not zero). The cause was not isolated. The likely cause, per-row FK triggers plus a 4-column PK, is an unverified hypothesis (`commit_variants.py` would test it). |
| Whole (c)+(d)+(e), clean file | 86.4 client wall | client 38 | |

## Planted errors (`demand_history_planted.csv`, python mode): PASS

`run_stages.sh planted` asserts this exact set and printed `planted_check: PASS` (no missing and no unexpected errors). Each error is reported as file, line, column and reason:

| Line | Column | Code | Reason |
|---|---|---|---|
| 11 | (row) | MALFORMED | expected 5 fields, found 4 |
| 12 | date | MALFORMED | not a valid YYYY-MM-DD date (`2026-02-30`) |
| 13 | quantity | MALFORMED | not a number (`abc`) |
| 14 | basis | MALFORMED | must be demand or sales |
| 21 | location_id,product_id,date | DUPLICATE | duplicate of line 20 |
| 31 | quantity | NEGATIVE | quantity must be >= 0 |
| 32 | quantity | FRACTIONAL | quantity must be a whole number |
| 41 / 42 | location_id / product_id | UNKNOWN_ID | not in locations.csv / products.csv |
| 51 | date | AFTER_AS_OF_DATE | after as_of_date (no future history) |
| 61 | location_id | MALFORMED | required value is blank |
| 4,500,002 | (row) / date | OVER_ENVELOPE | 4,500,001 data rows (limit 4,500,000); date more than 90 days before as_of_date |
| inventory.csv 4, 5, 7 | expiry_date / non_expiring | MISSING_EXPIRY / MALFORMED | neither expiry nor non_expiring; both given; `yes` |

- Line 71, a valid quoted row, is correctly **not** reported in python mode.
- Blank `quantity` is not an error, and it stays NULL through the commit.
- Strictness choice: `3.0` counts as FRACTIONAL.

## Recommendations (feeds W0-07 / W0-08)

1. **Upload mechanism: one streamed upload per file, then a durable `import.v1` job.**
   - Store the upload to disk and record its sha256 and byte count. The job reads it from disk, so a retry needs no re-upload.
   - The measured pipeline after upload (~86 s, client RSS 38 MB) fits a job well. Each step is independent of request lifetime.
   - Chunked uploads are not justified by these numbers, but the upload itself was **not measured**. Re-decide only if (a) shows a problem.
   - Exempt exactly the upload path from `RequestBoundary` in `main.py`. Enforce a byte cap of about 160 MB (143 MB max envelope plus headroom) while streaming. Rejection is 413 with the limit.
   - Use a streaming multipart parser (python-multipart `MultipartParser`) or FastAPI `UploadFile`. Which one to use depends on the unmeasured (a) results.
2. **Proxy: the browser posts the upload directly to the API (same-origin through compose/Fly routing), or the proxy gets a dedicated streaming branch.**
   - The current proxy cannot carry it: it buffers the full body, caps it at 64 KB and has a 20 s timeout.
   - Recommendation: a dedicated streaming branch for `POST imports/{id}/files/{name}`. It passes `request.body` through with `duplex: "half"`, counts bytes and has no 20 s timeout. This keeps the CSRF and origin checks in one place.
   - Whether Next 16's server wrapper buffers route-handler bodies is **unverified**.
3. **Staging table: UNLOGGED, all-text, one row per CSV record.**
   - Columns: `(import_id, file, line_no bigint, ncols int, <template columns as text>)`, loaded by Python `csv.reader` → `COPY … write_row`.
   - Recommended shape: a static parent from the migration, `PARTITION BY LIST (import_id)`, with one partition per import. The job creates the partition and drops it after commit or abort, so there is no bloat. Whether PG16 accepts UNLOGGED per-partition tables is **not verified**. The fallback is one UNLOGGED table per import, created by the job.
   - Keep raw text so every malformed value can be echoed.
4. **Import-errors table:** `import_errors(import_id, file, line_no, column_name NULL, code, reason, value NULL)`.
   - `column_name` is NULL for row-level errors. Codes: `MALFORMED, DUPLICATE, NEGATIVE, FRACTIONAL, UNKNOWN_ID, MISSING_EXPIRY, AFTER_AS_OF_DATE, OVER_ENVELOPE`.
   - Report `ORDER BY file, line_no LIMIT 1000`, plus a `more_than_cap` flag.
   - Keep validation set-based, with one query per class. Avoid per-row LATERAL fan-out over the full table.
5. **Commit:** keep the error-table gate plus a single transaction. Atomicity was shown: the forced bad insert left 0 rows.
   - 62–66 s and a 312 MB backend peak is the dominant phase.
   - Before W0-07 freezes the target, run `commit_variants.py`. It compares load-then-add PK/FK, and PK-only, against the per-row FK triggers. Consider per-dataset-version partitions attached after load.
6. **Job contract fields:** `phase ∈ {uploading, staging, validating, committing, done, failed}`, `files[]`, `progress: {unit: "bytes" | "rows" | "checks", done, total}`, `error_count`, `errors_truncated`, `import_id`, `dataset_version_id` (set on done), `input_sha256`.
   - Units per phase: uploading in bytes; staging in rows (total = file lines − 1); validating in checks (8 classes per file); committing in rows.
   - On failure, `failed` keeps the error rows and writes nothing to the target.

## Limitations

- Stage (a) and the faster-commit variants were not measured.
- Every number comes from one run on one laptop, with default PG settings.
- Parallel-worker memory is not included in the PG peak column.
- Docker Desktop on Windows was not tested.
- Database tables were dropped at the end; `s4_*` will not remain in `w0_s4_test`.
