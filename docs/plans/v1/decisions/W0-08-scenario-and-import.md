# W0-08 decisions: a new v1 scenario package, and import as create → upload files → commit

**Status:** decided by Gabriel, 2026-11-06. **Applies to:** W0-08 (contract freeze), the README "Interfaces frozen in W0-08" table, and the `w1-data`, `w1-solver` and `w1-web` lanes.

## 1. Scenario format: option A, a new `or-input-v3` package (v2 untouched)

`ORInputPackage` (`apps/api/app/schemas/or_inputs.py:294`, `schema_version "or-input-v2"`) can't carry a v1 network. It caps sites at 14 (`:304`), products at 8 (`:305`) and route ETA at 2 days (`:233`). It has no HUB/BENEFICIARY roles, no network mode, no USD unit values and no Retail weights. Raising those caps would change the existing v2 flow, which V1-A22 keeps unchanged.

- v1 scenarios use a new package in `apps/api/app/schemas/v1_planning.py` with `schema_version "or-input-v3"`, frozen and hashed the same way as v2. Its caps come from `v1_envelope.py`: 100 locations and 500 products.
- It carries the network mode, `LocationRole`, `Measure`, the optional `unit_value_usd`, `w_exp`/`w_lost`, and `travel_days` routes.
- The v3 method result reports each product's native solve status and gap. It labels unsolved products "not at risk; not optimized" ([W0-optimizer-decomposition.md](W0-optimizer-decomposition.md) §1, §4).
- `or-input-v2`, `or-comparison.v2` and their routes stay byte-for-byte. Only `or-comparison.v3` reads v3.

**Rejected, option B:** raise the v2 caps and add optional fields. It's less code, but every v2 hash, cap test and connected flow would be re-validated, and A22 would be at risk.

## 2. Import routes: the S4 proposal

Source: [S4-bulk-import.md](../spikes/S4-bulk-import.md), recommendations 1, 2 and 6.

| Route | Does | Returns |
|---|---|---|
| `POST /imports` | JSON with either `{network: {name, mode, timezone}}` (new network) or `{network_id}` (re-import). For a new network, creates its organization and an `import_runs` row in phase `uploading` that holds the pending network (`new_network`); the network row itself is created only by a successful commit (§4). A re-import uses the existing network. | 201 `ImportCreated{import_id, network_id}` (`network_id` is null for a new network) |
| `POST /imports/{import_id}/files/{name}` | One template file as a raw `text/csv` body, streamed from `request.stream()` (no multipart: the name is in the path, and a fixed content type avoids Windows labeling `.csv` as `application/vnd.ms-excel`; S4 measured raw-body uploads flat too). Byte cap of 160 MiB, counted while streaming. Stored on the `imports` volume shared by `api` and `worker`, and recorded in `import_runs.files` with its byte count and sha256. Re-posting the same name replaces the file. | 200 `ImportFile{name, bytes, sha256}`; 413 naming the limit (partial file deleted); 409 once the import has left `uploading` |
| `POST /imports/{import_id}/commit` | JSON `{as_of_date?}`. The value travels in the job payload, and when absent the job defaults it to the day after the last history date (V1-SPEC §6.1). Required files are checked before the job is admitted. | 202 `ImportAccepted{import_id, job_id}` (`import.v1`); 422 naming the missing files |
| `GET /imports/{import_id}` | Job-backed status | `ImportStatus{phase, files[], progress{unit, done, total}, error_count, errors_truncated, errors[RowError], outside_horizon_inbound[], dataset_version_id}` |

- **Phases and units** follow `IMPORT_PHASES` (`apps/api/app/models/networks.py:19`): bytes while `uploading`, rows while `staging`, checks while `validating`, rows while `committing`. At most 1,000 errors are reported, and `errors_truncated` says whether there were more.
- **API boundary:** `RequestBoundary` (`apps/api/app/main.py:54`) exempts exactly the file route. That route enforces its own byte cap. Every other path keeps the 64 KB limit.
- **Proxy:** a dedicated streaming branch for the file route only. It passes the body through (`duplex: "half"`), counts bytes against the same cap, and has no 20 s timeout. Origin, CSRF and proxy-token handling stay as they are. The current proxy buffers bodies and caps them at 64 KB (`apps/web/src/app/api/v1/[...path]/route.ts:83-107`).
- **Next 16 streaming risk: resolved, 2026-11-06.** S4 never checked whether Next's own server buffers route-handler bodies. `apps/web/scripts/check-upload-streaming.mjs` runs the real standalone server (`NEXT_OUTPUT=standalone`, as in `apps/web/Dockerfile`) against a byte-counting sink in place of the API, at S4's 20 MiB/s.
  - The sink got its first byte after the client had sent 1 MiB, in both a 50 MiB and a 150 MiB run. Next does not buffer.
  - All 150 MiB arrived in 7.6–7.7 s.
  - Server RSS grew 38.4 MiB for 50 MiB and 46.6 / 56.6 MiB for 150 MiB. That's bounded garbage, not buffering: tripling the body added only 8–18 MiB.
  - An unthrottled loopback run (0.22 s) peaked at +96.9 MiB. That's uncollected garbage at about 680 MB/s; the sink again got its first byte at 1 MiB.
  - Single runs on one WSL laptop. The check passes under a 64 MiB growth limit.

**Consequences, owned by W1-D05:**
- An abandoned import leaves a network with no dataset version. The network list shows it as "import not finished".
- Uploaded files are deleted after a commit or an abort. Cleanup of abandoned uploads is an open item.

**Rejected alternatives:**
- **One request carrying all files and the commit:** one bad row forces every file to be re-sent, and the run outlasts the proxy timeout, which breaks the durable-job rule.
- **All files in one request, then a commit job:** a larger cap, and still a full re-send.
- **Chunked or resumable upload:** solves nothing on loopback; a 143 MB stream took 0.37 s.
- **Browser straight to the API:** the API isn't published, and this breaks the same-origin proxy rule (V1-SPEC §4).
- **A mounted `./import/` folder:** moves the guided import out of the UI (V1-SPEC §1, step 2), adds Windows bind-mount and path friction against A18, and makes the inputs mutable. It's a possible power-user extra later, not v1.
- **One zip of all CSVs:** needs zip-bomb limits and per-member error paths, and gains nothing on loopback.

## 3. Follow-on contract calls (Gabriel, 2026-11-06)

- **v1 forecasts and comparisons live under `/networks/{id}/…`:** `POST /networks/{id}/forecasts`, `POST /networks/{id}/comparisons`, `GET /networks/{id}/comparisons/{comparison_id}`, and its `methods/{method}/actions` and `methods/{method}/export`. Extending `POST /comparisons`, `GET /comparisons/{id}` and `POST /forecasts` would have changed v2's request and response models.
- **Unbuilt routes answer 501 in the existing error envelope:** `{"error": {"code": "NOT_IMPLEMENTED", "message": ..., "details": {"task": "<task id>"}}, "request_id": ...}`. The web client keeps one error parser, and the request ID is kept.
- **New job kinds `IMPORT` and `ENRICHMENT`:** migration `ppv1_0009` widens `compute_jobs_operation_kind_check`, and `RuntimeProfile` gains `import_total_s` and `enrichment_total_s` (300 s each). Job rows say what they are. `or-comparison.v3` stays `COMPARISON`. Reusing `FORECAST` would have avoided the migration but mislabeled every import job.
- **Uploaded files live on the `imports` volume** (`PP_IMPORT_DIR=/var/lib/pantrypulse/imports`). `api` writes it and `worker` reads it; `web` never mounts it.

## 4. Atomic import (Gabriel, 2026-11-06)

An import either succeeds completely or leaves nothing behind, including the network itself.

- **Network creation:** migration `ppv1_0010` makes `import_runs.network_id` nullable and adds `new_network` (`{name, mode, timezone}`). The `import.v1` commit inserts the `networks` row in the same transaction as the dataset version and every data row. A failed or abandoned first import leaves no network; the network list never shows it. CHECK constraints: a run has a network or a pending one, and a `done` run has its network.
- **What remains after a failure:** the import run, its errors and its uploaded files, so the user can read the report. They aren't network data. Their organization row stays as internal bookkeeping; cleanup of abandoned runs and files is W1-D05's open item.
- **The failure message:** `ImportStatus.failure` is set exactly when `phase = failed`. It has `kind` (`ROW_ERRORS`, `MISSING_FILES`, `OVER_ENVELOPE`, `JOB_FAILED`), a `message` that starts "Import failed" and says nothing was saved, a `reason` (why), and at least one `next_steps` entry (what to do instead). Every `RowError` has a `fix` saying what to change in the file, stored in `import_errors.fix` so the report survives the job. Guidance text is never blank.
- **Rejected alternative:** keep creating the network first and hide it from the list on failure. The row would still exist, which breaks "nothing is saved" (V1-SPEC §6.1).
