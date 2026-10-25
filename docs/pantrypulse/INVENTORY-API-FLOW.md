> [Current VP convergence](VP-API-INTEGRATION.md) supersedes conflicting branch-only contracts. Dated evidence below remains historical.

# Inventory snapshot API (PP-46)

Implemented on local VP. The snapshot GET inspects current physical inventory;
the PP-47 adjustment POST below corrects existing lots with an audited command.
Neither requires a forecast worker. GET never creates or adjusts stock.

```text
Browser / HTTP client
  → Next /api/v1/inventory/sites/{site_id}/products/{product_id}
  → FastAPI presenter authentication (server-selected organization)
  → PostgreSQL repeatable-read transaction
  → site + product + calendar + inventory version + positive-balance lots
  → classify each lot once and return totals + lot details
```

Use the existing `POST /api/v1/presenter/login` credentials/session. Retrieve real
IDs from `GET /api/v1/forecast-catalog`, then call:

```http
GET /api/v1/inventory/sites/{site_id}/products/{product_id}
Cookie: pp_presenter=<session from login>
```

The same path works through the Next proxy or directly against FastAPI. The
proxy only forwards selected session cookies. Credentials remain server-side.

The response contains `site_id`, `product_id`, their names, `base_unit`,
`timezone`, `local_date`, `observed_at`, `inventory_version`, `on_hand_quantity`,
`usable_quantity`, `excluded_quantity`, `excluded_quantities` and `lots`.
Quantities and versions serialize as **decimal strings**, preserving PostgreSQL
BIGINT precision in browser clients. A missing saved inventory version is `null`;
this GET never creates a version row. Valid empty stock returns zero quantities
and an empty lot list. The demo history loader creates no physical stock, so
empty inventory in that demo is expected.

Each lot includes its batch key, positive on-hand balance, eligibility, expiry
declaration, expiry date, metadata version, usability and exclusion reason.
Totals are for exactly one product in its base unit; units are never combined.

Classification order is explicit and disjoint: held/ineligible/unknown eligibility,
then unknown expiry, then expired. A held expired lot appears only in `HELD`.
Dated lots remain usable through their expiry date in the site's timezone;
explicitly non-expiring eligible lots remain usable. Future confirmed arrivals
are not physical stock. Usable quantity is not a transfer allowance: donor
reserves, local demand protection, routing and scenario commitments belong to
planning. There is no reservation workflow in this endpoint.

Missing or other-tenant site/product IDs return 404. Missing/invalid site calendar
returns 503. Malformed UUIDs return 422, missing session returns 401, and more than
500 positive-balance lots returns `422 INVENTORY_TOO_LARGE` rather than partial
totals. Reads use a 10-second statement timeout and return no-store/request-ID
headers. Historical/as-of queries and receipt/lot creation remain separate work.

## Audited adjustment API (PP-47)

```http
POST /api/v1/inventory/sites/{site_id}/products/{product_id}/adjustments
Origin: http://127.0.0.1:8000
Cookie: pp_presenter=<session from login>
X-CSRF-Token: <csrf_token returned by login>
Idempotency-Key: count-note-001
Content-Type: application/json

{
  "expected_inventory_version": "2",
  "reason": "Physical count found five fewer meals",
  "source_reference": "count-note-001",
  "changes": [
    {"lot_id": "<existing lot UUID from inventory GET>", "delta": "-5"}
  ]
}
```

Read the snapshot first and copy its saved `inventory_version` and the actual
lot ID. Copy the **current** version; the example's `"2"` is illustrative. The
body accepts 1–100 distinct existing lots belonging to that site/product. Delta
is a signed nonzero quantity in that product's base unit: `"5"` adds five and
`"-5"` removes five. Versions and deltas must be canonical decimal **strings**,
not JSON numbers, with magnitude at most 9223372036854775807. Provide a nonblank
reason (≤1000 characters), source reference (≤256), and command key (≤128).
Actor/organization come from the authenticated session and cannot be supplied
in JSON. This corrects physical counts; it does not revise receipt history,
declarations or expiry, reserve/dispatch goods, or complete transfers.

The response is 200 only after commit and includes `status: APPLIED`, `command_id`,
site/product IDs, `before_version`, `after_version` and each changed lot's exact
before/after quantity. Stock, inventory version, immutable command, signed ledger
entry and audit event commit in one transaction. Read inventory again for current
usable/excluded totals after the command.

An identical request with the same idempotency key and authenticated actor returns
the original saved result without moving stock again, even though its expected
version is now older. A changed request using that key returns
`409 IDEMPOTENCY_CONFLICT`. A new command using a stale version returns
`409 STALE_INVENTORY_VERSION`; refresh stock and review the correction before
submitting another command. Competing new commands with one expected version can
have only one winner. Do not generate a new key merely because a request timed out;
retry the original body/key to learn its committed outcome.

Insufficient stock or count overflow returns 422; stock/ledger/version/audit remain
unchanged. Missing, mismatched or cross-tenant lots return 404. Authentication,
Origin and CSRF are enforced. Server/database errors use the existing redacted
request-ID error envelope. Transactions have a 10-second statement timeout.

### Swagger locally

Restart Uvicorn if it was started without `--reload`, then refresh
`http://127.0.0.1:8000/docs`. Login in that browser, copy its response's
`csrf_token`, retrieve a snapshot, then expand the POST above. Fill site/product,
`X-CSRF-Token`, `idempotency-key` and the JSON body using real IDs/current version.
The browser session supplies the cookie and local Origin. The existing same-origin
Next proxy also permits this exact POST and forwards the two command headers.

The persistent demo contains history but no physical stock. This API deliberately
cannot create a first lot, and a null inventory version cannot be used as a saved
version. Receipt posting/lot creation is the next separate API work; do not insert
ad hoc SQL or invent lot IDs just to obtain a successful adjustment.

Verification commands:

```powershell
cd apps/api
.venv/Scripts/python.exe -B -m pytest tests/test_inventory_api.py -q -p no:cacheprovider
# Integration requires PP19_TEST_DATABASE_URL and PP19_TEST_SCHEMA_ISOLATION=1;
# fixtures create/drop only their own generated schema, never persistent demo data.
.venv/Scripts/python.exe -B -m pytest tests/integration/test_inventory_api_postgres.py -q -p no:cacheprovider
.venv/Scripts/python.exe -B -m pytest tests/test_stock_adjustment_api.py tests/integration/test_stock_adjustment_api_postgres.py -q -p no:cacheprovider
```

Integration coverage includes authenticated reads, excluded/empty stock, exact
large integers, missing/cross-tenant IDs, no GET writes, oversized snapshots and
a concurrent balance/version change. Tests are implementation evidence; full
browser integration and independent release review remain separate gates.
