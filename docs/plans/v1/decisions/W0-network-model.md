# W0 decision: how a v1 network maps to the tenant model

**Status:** decided by the lead for W0-07, 2026-11-04, following the wave-0 recommendation. The local-login placement was approved by Gabriel on 2026-11-04. **Applies to:** migration `ppv1_0008`, `app/models/networks.py`, W0-05 and W0-08.

## Decision

1. **One organization per network.** Creating a network creates its own `organizations` row, and the `networks` row references it 1:1 (`networks.organization_id` is unique). Every v1 table carries `organization_id` with the existing composite tenant foreign keys, so `forecast.v1`, the projection, the scenario code and the dashboard keep their organization scoping unchanged.
2. **The local presenter session may read every network of the install.** The install has one local user. The backend resolves the session to the set of organizations whose network belongs to this install, and authorizes each request against the network it names (`network_id` in the path or body). It never trusts an organization ID sent by the client. The routers in W0-08 implement this; the existing single-organization presenter path stays as it is for the v2 flow.
3. **The local login is stored in the database (Gabriel, 2026-11-04).** `ppv1_0008` adds a `local_logins` table with the username and the scrypt hash only. The backend reads the hash from that table when `PP_PRESENTER_PASSWORD_HASH` is unset; the environment variable keeps working for hosted and test setups. The plaintext password exists only in `.pantrypulse/local-login.txt` (mode 0600) on the host. **Consequence:** W0-05 runs after W0-07.
4. **The proxy token is not stored in the database.** The `seed` service generates it once into a file on a volume shared with `api` and `web` (W0-05). It is never passed through `eval` and never printed.

## Schema as built in `ppv1_0008`

- **Tenant tables** (`Base.metadata`, every row carries `organization_id`): `networks`, `import_runs`, `dataset_versions`, `import_events`, `import_errors`, `net_locations`, `net_products`, `net_batches`, `net_demand_history`, `net_donation_history`, `net_inbound`, `net_routes`, `backtest_scores`. The `net_` prefix avoids the existing v2 `products` table.
- **Install-wide tables** (`install_metadata`): `import_staging`, `google_distance_cache`, `local_secrets`, `local_logins`.
- **`as_of_date` lives on `dataset_versions`, not on `networks`.** Each re-import is a new version with its own snapshot date, and a scenario must keep the date of the version it used. `networks` holds the mode (fixed by trigger) and the timezone.
- **Immutable by trigger:** `dataset_versions` and `import_events`. The network mode can't change.
- **Partitioning (S4):** `net_demand_history` and `net_donation_history` are LIST-partitioned by `dataset_version_id`. The import job loads each version into a partition created `LIKE` the parent `INCLUDING CONSTRAINTS`, adds the keys, then attaches it. `import_staging` is LIST-partitioned by `import_run_id`, with one UNLOGGED partition per run, dropped after commit or abort (PG16 accepts UNLOGGED partitions, checked 2026-11-04). Staging has no foreign keys, so COPY stays fast; ownership goes through `import_runs`.
- **A network row exists from the first import attempt.** `import_runs` needs it. A network with no dataset version means "not imported yet".

## Why

- Reusing the organization as the tenant keeps every existing query, constraint and test valid. A new `network_id` tenant column would touch every v2 table and router.
- Per-network organizations keep sample networks and user networks fully separated, and a later "delete network" can drop one tenant.
- A database row for the login survives `docker compose restart` and image upgrades, and it disappears together with the install's data on `docker compose down -v`. That matches "start over".

## Rejected

- **One organization for the whole install, with `network_id` on every row.** It needs new scoping on every v2 query, and a missing filter would leak data across networks.
- **Login hash in a shared-volume file.** It's smaller, but it splits the install's state between the database and a volume, and the W0-05 test asks for the database.
