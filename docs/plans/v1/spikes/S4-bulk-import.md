# Spike S4: bulk import at 4.5 M rows (W0-03)

Status: measured. Stages (a) through (e) were measured, plus four commit variants with planted-failure atomicity checks (follow-up run on branch `spike/w0-s4b`, 2026-11-04). The end-to-end (c)+(d)+(e) wall time with the recommended commit variant was **not re-measured**. Spike code is throwaway: `apps/api/spikes/s4/`.

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

Follow-up run (`spike/w0-s4b`, base `4ee2a24`, same machine, regenerated data with the identical sha256):

```
bash spikes/s4/run_upload.sh                     # stage (a), loopback at full speed
RATE=20M bash spikes/s4/run_upload.sh            # stage (a), client throttled to 20 MB/s so RSS can be sampled
.venv/bin/python spikes/s4/commit_variants.py spikes/s4/out fail         # e1..e4, each also with a planted duplicate
.venv/bin/python spikes/s4/commit_variants.py spikes/s4/out e1 e4 fail   # repeat of e1 and the fixed e4
```

Script fixes in that run: a streaming byte cap (`?cap=`) and an RSS sampler were added; the failure injection matched `INSERT` after leading whitespace; the e4 partition is created with `LIKE … INCLUDING CONSTRAINTS` (the first e4 attempt failed `ATTACH` with `child table is missing constraint "s4_target_basis_check"` and rolled back, 0 rows).

## Measurement method

- Every step runs on a fresh connection.
- "PG peak" is that backend's `VmHWM`, read from `/proc` in the container. It includes shared buffers the backend touched. It **excludes parallel workers**.
- "Client peak" is the `/usr/bin/time` max RSS of the whole Python process.
- Times are wall seconds from one run each. The variance column is a second run where one exists.

## Results

| Stage | Seconds | Peak MB | Notes |
|---|---|---|---|
| (a) FastAPI multipart upload, 143 MB | 0.37–0.85 loopback; 6.6–6.7 at 20 MB/s | server 86.9–96.3 (idle 82–91) | Flat: peak minus idle is 2–6 MB for a 143 MB body. Details in the stage (a) table below. `main.py` `RequestBoundary` still reads the whole body before routing, so the spike route bypasses it by path; the real app path still returns 413. |
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
| (e) commit 4.5 M rows into a target with PK + 2 FKs, one transaction | **61.6 / 65.8** | **312** | The biggest cost. The target was 454 MB afterwards, with 90,033 NULL quantities preserved (not zero). Re-measured in the follow-up at 27.7 / 35.0 / 44.9 s (same shape, high run-to-run variance). The commit-variants table below isolates the cause: per-row FK triggers. |
| Whole (c)+(d)+(e), clean file | 86.4 client wall | client 38 | |

## Stage (a): FastAPI upload of `demand_history.csv` (143,097,619 bytes)

One fresh uvicorn per variant on 127.0.0.1:8031 (`upload_app.py`). Only `/spike/s4/*` bypasses `RequestBoundary`; every other path goes to the unchanged `create_app()`. "Server peak" is `/usr/bin/time` max RSS of uvicorn over its whole life, including the extra requests listed. "During upload" is the uvicorn RSS sampled every 0.1 s. Every successful upload returned the source sha256 `018d6ec9…c393` and byte count.

| Variant | Client rate | Wall s | Server peak MB | Idle MB | RSS during upload MB | Notes |
|---|---|---|---|---|---|---|
| `UploadFile` (Starlette form parse, spooled temp file, then copied) | loopback | 0.85 | 96.3 | 91 | 94 (1 sample) | 0 spool files left in TMPDIR. |
| same | 20 MB/s | 6.70 | 86.9 | 82 | 83–85 (62 samples) | Flat. |
| `MultipartParser` streamed straight to the destination file | loopback | 0.37 | 88.0 | 82 | no sample (faster than 0.1 s interval) | Peak includes the cap test. |
| same | 20 MB/s | 6.59 | 87.9 | 82 | 83–85 (60 samples) | Flat. |
| raw-body chunks, 9 × 16 MiB `POST`s | loopback (both runs) | 0.60–0.69 | 87.2–87.5 | not sampled | not sampled | Peak includes the real-route probe. |
| streaming byte cap `?cap=10000000` | loopback / 20 MB/s | 0.03 / 0.50 | (in stream row) | | | **413** `INPUT_TOO_LARGE` after reading 10,144,768 bytes; partial file deleted. |
| real app path `/api/v1/imports/demand/csv` | loopback | | | | | 413 from `RequestBoundary` (64 KB), as before. |

- Neither variant buffers the whole body: memory stays within 2–6 MB of idle for a 143 MB upload.
- A byte cap **can** be enforced while streaming with `MultipartParser`: count `request.stream()` bytes and stop at the limit, without trusting `Content-Length`. Measured above.
- With `UploadFile`, FastAPI parses the whole multipart body before the handler runs, so the handler cannot cap it. It would need an ASGI `receive` wrapper. **Not measured.**
- `UploadFile` writes every byte twice (spool, then destination). The disk cost of that was **not measured**; wall time was 0.85 s against 0.37 s on loopback.
- Loopback only. A real network, the Next proxy and Fly routing were not in the path.

## Commit variants: 4,500,000 rows, one transaction each

`commit_variants.py`: staging loaded once (python mode, UNLOGGED), then each variant runs on a fresh connection in **one transaction**. Setup outside the timed transaction stands in for migration-owned tables. "_FAIL" plants one duplicate key directly after the bulk INSERT. "PG peak" is backend `VmHWM` (includes touched shared buffers, excludes parallel workers).

| Variant | Seconds (statement split) | PG peak MB | Planted failure: seconds, outcome, target rows |
|---|---|---|---|
| e1 current shape: PK + 2 FKs, one INSERT | 44.92, 27.70, 35.03 (earlier run: 61.6, 65.8) | 313 | 33.63 / 33.52 s, `UniqueViolation` on the INSERT, rolled back, **0** |
| e2 PK only, no FK, one INSERT | 6.29 | 210 | 6.24 s, `UniqueViolation`, rolled back, **0** |
| e3 bare table, INSERT, then ADD PK, ADD both FKs | 5.01 (insert 3.52, PK 1.00, FK 0.48) | 274 | 4.14 s, `could not create unique index`, rolled back, table absent (**0**) |
| e4 bare per-version table, INSERT, ADD PK, ADD FKs, ADD CHECK, ATTACH to PK+FK parent | 5.20 (insert 3.57, PK 0.97, FK 0.50, CHECK 0.14, ATTACH 0.00) | 274 | 4.45 / 4.24 s, `could not create unique index "s4_target_v1_pkey"`, rolled back, parent **0** |

- The cause of the slow commit is the per-row FK triggers: e1 minus e2 is 21–39 s in this run set. The 4-column PK costs about 1 s when built in bulk.
- All four variants keep all-or-nothing: every planted failure left 0 target rows.
- `ATTACH` took 0.00 s, so the partition's matching PK and FKs were reused and the CHECK let it skip the partition-constraint scan.
- e3 only works for an empty target. On a shared table that already holds other dataset versions, `ADD PK` would rebuild the index over every version. e4 costs scale with the new version only.
- e1 varied from 27.7 to 65.8 s across five runs (the two earlier ones are `stage.py` `e_commit` into the same shape); e2–e4 were within about 1 s of each other across their runs. The variance cause was not investigated.

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
   - Chunked uploads are not justified: a single streamed 143 MB upload kept server RSS within 6 MB of idle and took 0.37 s on loopback (stage a).
   - Exempt exactly the upload path from `RequestBoundary` in `main.py`. Enforce a byte cap of about 160 MB (143 MB max envelope plus headroom) while streaming. Rejection is 413 with the limit and the partial file is deleted (measured).
   - Use python-multipart `MultipartParser` on `request.stream()`, not `UploadFile`. Both stay flat in memory, but only the streaming parser lets the handler enforce the byte cap mid-stream, and it writes each byte once (0.37 s against 0.85 s).
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
5. **Commit:** keep the error-table gate plus a single transaction, and load into a **per-dataset-version partition** attached after load (variant e4).
   - The target parent is `PARTITION BY LIST (dataset_version_id)` with the PK and both FKs. The job, in one transaction: `CREATE TABLE … (LIKE parent INCLUDING CONSTRAINTS)`, bulk INSERT from staging, ADD PK, ADD both FKs, ADD `CHECK (dataset_version_id = N)`, `ATTACH PARTITION`.
   - Measured 5.2 s and a 274 MB backend peak, against 27.7–65.8 s and 313 MB for the current shape. A planted duplicate rolled back with 0 rows.
   - The child's CHECK constraint names must match the parent's, or `ATTACH` fails. `LIKE … INCLUDING CONSTRAINTS` handles that.
   - Do not use e3 (drop and re-add constraints on one shared table): it only works while the table is empty.
6. **Job contract fields:** `phase ∈ {uploading, staging, validating, committing, done, failed}`, `files[]`, `progress: {unit: "bytes" | "rows" | "checks", done, total}`, `error_count`, `errors_truncated`, `import_id`, `dataset_version_id` (set on done), `input_sha256`.
   - Units per phase: uploading in bytes; staging in rows (total = file lines − 1); validating in checks (8 classes per file); committing in rows.
   - On failure, `failed` keeps the error rows and writes nothing to the target.

## Limitations

- Not measured: end-to-end (c)+(d)+(e) with e4; e4 when the parent already holds other versions or other tables reference it by FK; `ATTACH` lock impact on concurrent readers; an `UploadFile` byte cap; upload over a real network or through the Next proxy and Fly.
- Every number comes from one run on one laptop, with default PG settings.
- Parallel-worker memory is not included in the PG peak column.
- Docker Desktop on Windows was not tested.
- Database tables were dropped at the end; `s4_*` will not remain in `w0_s4_test`.
