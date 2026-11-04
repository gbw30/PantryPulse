# W0 decision: how a v1 network maps to the tenant model

**Status:** decided by the lead for W0-07, 2026-11-04, following the wave-0 recommendation. The local-login placement was approved by Gabriel on 2026-11-04. **Applies to:** migration `ppv1_0008`, `app/models/networks.py`, W0-05 and W0-08.

## Decision

1. **One organization per network.** Creating a network creates its own `organizations` row, and the `networks` row references it 1:1 (`networks.organization_id` is unique). Every v1 table carries `organization_id` with the existing composite tenant foreign keys, so `forecast.v1`, the projection, the scenario code and the dashboard keep their organization scoping unchanged.
2. **The local presenter session may read every network of the install.** The install has one local user. The backend resolves the session to the set of organizations whose network belongs to this install, and authorizes each request against the network it names (`network_id` in the path or body). It never trusts an organization ID sent by the client. The routers in W0-08 implement this; the existing single-organization presenter path stays as it is for the v2 flow.
3. **The local login is stored in the database (Gabriel, 2026-11-04).** `ppv1_0008` adds a `local_logins` table with the username and the scrypt hash only. The backend reads the hash from that table when `PP_PRESENTER_PASSWORD_HASH` is unset; the environment variable keeps working for hosted and test setups. The plaintext password exists only in `.pantrypulse/local-login.txt` (mode 0600) on the host. **Consequence:** W0-05 runs after W0-07.
4. **The proxy token is not stored in the database.** The `seed` service generates it once into a file on a volume shared with `api` and `web` (W0-05). It is never passed through `eval` and never printed.

## Why

- Reusing the organization as the tenant keeps every existing query, constraint and test valid. A new `network_id` tenant column would touch every v2 table and router.
- Per-network organizations keep sample networks and user networks fully separated, and a later "delete network" can drop one tenant.
- A database row for the login survives `docker compose restart` and image upgrades, and it disappears together with the install's data on `docker compose down -v`. That matches "start over".

## Rejected

- **One organization for the whole install, with `network_id` on every row.** It needs new scoping on every v2 query, and a missing filter would leak data across networks.
- **Login hash in a shared-volume file.** It's smaller, but it splits the install's state between the database and a volume, and the W0-05 test asks for the database.
