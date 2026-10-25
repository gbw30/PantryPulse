# Neon PostgreSQL setup

Purpose: host the dedicated PostgreSQL database for the online demo. Local development continues to use Docker PostgreSQL. Follow [GitHub setup](GITHUB.md) first; continue with [personal-computer demo setup](LOCAL-DEMO.md) or the optional [Fly.io](FLY.md) alternative. The external service workflow is in [EXTERNAL-SERVICES.md](../../EXTERNAL-SERVICES.md).

## Manual account/project setup

1. Sign in at https://console.neon.tech, creating an account if needed.
2. Reuse an existing authorized PantryPulse project if one exists; otherwise create a dedicated project such as pantrypulse.
3. For the laptop demo, keep the region of the project already created and measure connectivity. There is no Fly region to match. Use PostgreSQL 16 if offered to match local development; if selecting another major version, record it and test schema/migration compatibility rather than assuming equivalence.
4. Create or identify a database for the synthetic demo, such as pantrypulse_demo.
5. Keep test/preview work separate from the judge-demo database. For schema testing, create a child branch from the intended synthetic-data branch and use that branch's own endpoint.
6. Review the selected plan's compute, storage, branch and restore limits in the dashboard.

These are project choices, not provider-required names. See the [console guide](https://neon.com/docs/get-started/signing-up) and [branch documentation](https://neon.com/docs/manage/branches).

## Recommended project settings

Reviewed against Neon's documentation on October 24, 2026. These are PantryPulse recommendations, not settings already applied to an account. Dashboard labels can vary; use the selected project and branch identifiers to confirm scope.

### Project creation form

| Field | Choose for PantryPulse | Reason |
|---|---|---|
| Organization | The team's intended organization/account | Keeps ownership, access and billing clear |
| Project name | `pantrypulse` or `pantrypulse-mvp` | A descriptive label; reuse an existing project if appropriate |
| Cloud provider | AWS, as offered in the region selector | Neon manages the infrastructure; no separate AWS account is needed to use Neon |
| Region | Keep the existing project's region for the laptop demo; East US is a reasonable new-project candidate for this event | No hosted backend region needs matching; measure laptop-to-database connectivity |
| Postgres database | Enabled | The only Neon service required for this architecture |
| Postgres version | **16**, if selectable | Matches the repository's local `postgres:16`; expand the Postgres service to inspect the version |
| Other services | Leave Auth, Data API, Functions, Object Storage, AI Gateway and Realtime disabled unless separately approved for a feature | FastAPI owns application access and business logic; those services are not needed for this MVP |
| Plan | Free for initial development if its allowances cover measured use | Upgrade only when an actual limit, recovery requirement or demo availability need warrants it |

If a future hosted backend is selected, prefer a nearby database region rather than automatically using Virginia. **A project's region cannot be changed in place.** Moving it later requires a new project and data migration. All branches in a project share its region. Sources: [project creation](https://neon.com/docs/manage/projects#create-a-project), [regions](https://neon.com/docs/introduction/regions).

Postgres 16 is a compatibility preference, not a reason to discard an existing populated project. If only a newer version is offered, record it and verify migrations/tests against that version before the demo. Do not assume the provider's default major version matches local development.

### Branch, database and role are separate selections

A **project** holds the whole environment. A **branch** gives an isolated version of the database contents. A **database** is a named database inside that branch. A **role** is the account used to connect.

| Resource | Recommended arrangement |
|---|---|
| Root/default branch | Use the existing root as the dedicated synthetic-demo branch; record its actual name and ID |
| Demo database | `pantrypulse_demo`, created/selected on that branch |
| Development branch | Create one child such as `dev` when hosted development or migration testing is needed and the plan permits it |
| Test database name | The child may keep `pantrypulse_demo`; its distinct branch endpoint supplies the isolation |
| Preview branches | Add deliberately when needed, with a known API mapping; Vercel previews do not create them automatically |
| Branch expiration | Optional for disposable preview/test branches; no automatic expiry on the judge-demo branch |
| Protected branch | Consider enabling protection for the frozen demo where the plan supports it; it does not replace application permissions or protected reset logic |

The root may be named `production` or `main`, depending on how the project was created. Neither spelling proves that a connection targets the right branch. A default database named `neondb` and owner role may already exist. You can use them deliberately or create the project-specific database; do not delete resources just to match this guide's names.

A child branch copies its parent's state at creation and then diverges. Parent changes do not automatically update it. Select the child's own endpoint before tests; changing only the database name does not switch branches. Plan allowances and compute/storage usage apply across the project. Source: [branch management](https://neon.com/docs/manage/branches).

Reserve the existing owner/admin role for initial setup and future migrations. For the eventual application, use a dedicated runtime role such as `pantrypulse_app` with only the required database, schema, table and sequence permissions. **Creating a role in the Console/CLI/API does not automatically make it restricted**: Neon documents that these roles inherit `neon_superuser` membership. Restricted roles should be created through reviewed SQL and receive deliberate grants. Domain schemas do not exist yet, so those grants are a later migration/setup task. Source: [database access](https://neon.com/docs/manage/database-access).

Neon team-member permissions and PostgreSQL roles are also different: console access lets a person manage the project; the database URL's role controls what a running application can do. Give team members only the project access they need rather than sharing one person's login.

### Compute size and scale to zero

The database stores data and answers queries. OR-Tools and optional Chronos calculations execute on **the laptop**, so increasing Neon compute does not give the Python solver more CPU or RAM.

| Setting | Development/testing | Judge demo |
|---|---|---|
| Compute type | One primary read-write compute on each branch that needs connections | One primary on the selected demo branch |
| Starting size | Fixed **0.25 CU**, if offered, or the smallest supported size | Start with the measured working size; raise it only if query latency/connections require it |
| Autoscaling | Unnecessary initially; a fixed size is simpler to measure | If enabled, set a deliberate upper bound based on testing and budget |
| Scale to zero | Enabled to reduce idle usage | On a supported paid plan, consider disabling it for the demo window; otherwise test and account for the database wake-up delay |
| Read replicas | None | None for the initial workload |

The 0.25 CU suggestion is a starting hypothesis for a small simulated dataset, not a tested capacity guarantee. Laptop/Docker resources are separate from Neon compute.

For **future computes**, open **Settings → Postgres → Compute defaults**. For an **existing compute**, select the correct branch, then **Postgres database → Computes → Edit**. Inspect its effective size and scale-to-zero configuration there. Changing project defaults does **not** resize or change suspension for existing computes. Source: [compute settings](https://neon.com/docs/manage/computes).

On Free, scale to zero remains enabled with a five-minute inactivity timeout. On supported paid plans it can be disabled. Keeping the laptop API running does not automatically keep Neon awake. Before presenting, run the database connectivity check and rehearse the full application path; a health-only request will not wake the database because that endpoint does not query it. Do not introduce a continuous artificial query loop as a substitute for choosing the intended service policy. Source: [scale-to-zero configuration](https://neon.com/docs/guides/scale-to-zero-guide).

### Project Settings tabs

| Setting area | Recommended action |
|---|---|
| General | Record project/branch IDs, confirm the default branch and ownership; avoid transfer/delete during setup |
| Postgres → Compute defaults | Set the defaults for future test branches; separately inspect the current demo compute |
| Postgres → History window | Keep the available restore history; choose a longer window only if its plan/cost is justified |
| Postgres → Updates | Review the schedule; if the plan allows customization, avoid the planned presentation window |
| Postgres → Logical replication | Leave disabled; the MVP has no replication pipeline |
| Networking | Use the standard authenticated TLS endpoint; configure IP restrictions only when the laptop's actual outbound network address and administrative access are accounted for |
| Data API / Auth / other services | Leave unneeded services disabled; the browser reaches data through FastAPI |
| Project permissions | Grant intended team members access at the appropriate level; do not share owner credentials |

An optional public tunnel address is not evidence of the address Neon sees for outbound database connections. If choosing an IP allowlist, first establish and test the laptop's actual egress configuration; switching venue networks can change it. No private-networking add-on is required for this synthetic MVP. Settings reference: [manage projects](https://neon.com/docs/manage/projects#project-settings).

Neon's current history window is **6 hours on Free**, with a 1 GB history cap; Launch defaults to **1 day** and permits up to **7 days**. For a paid weekend demo, a one-day window is a reasonable starting point if its cost is acceptable. Record the actual configured value. A restore window is not a substitute for versioned fixtures, migrations and a tested reset. History settings apply project-wide, and reducing the window to zero disables instant restore/Time Travel. Source: [history window](https://neon.com/docs/introduction/history-window).

Keep ordinary database parameter defaults initially. Store application timestamps consistently in UTC and verify the effective session time zone when the persistence layer is built; date-based simulated scenarios still use their explicit as-of date. No extra Postgres extension, vector database, or database-side solver is required by the current design.

### Settings to record before leaving the Console

Record these non-secret values in the environment/release notes:

- Project name/ID, organization, plan, AWS region and Postgres major version.
- Demo branch name/ID, database name, compute endpoint ID and role name.
- Effective compute size/autoscaling range, scale-to-zero policy and restore window.
- The separate dev/preview branch mapping, if any.

Keep passwords and full connection strings out of those notes. Review compute, branch, storage/history and transfer usage during testing; an autoscaling ceiling is not a total spending cap.

## Obtain connection details

In the project's Connect dialog, select the exact branch, database and role. Obtain:

| Connection | Planned use |
|---|---|
| Pooled endpoint | Application queries from FastAPI |
| Direct/unpooled endpoint | Alembic migrations and administration |

Use the returned endpoints; do not invent hostnames. Neon's [pooling documentation](https://neon.com/docs/connect/connection-pooling) explains the distinction. Copy credentials directly into the destination provider's secret configuration.

PantryPulse uses SQLAlchemy with psycopg 3, already installed. Do not install psycopg2 or a JavaScript database SDK just because another provider example uses it.

For SQLAlchemy, preserve the dashboard's encoded username/password, host, database and TLS query parameters, but use the driver prefix postgresql+psycopg://. Illustrative formats only:

```text
DATABASE_URL=postgresql+psycopg://USER:ENCODED_PASSWORD@POOLED_HOST/pantrypulse_demo?sslmode=require
DATABASE_URL_UNPOOLED=postgresql+psycopg://USER:ENCODED_PASSWORD@DIRECT_HOST/pantrypulse_demo?sslmode=require
```

Keep any additional connection-security parameters supplied by Neon. Credentials containing special characters must remain URL-encoded. These URLs are server-only.

## Connect the backend

For the selected laptop demo, store DATABASE_URL privately in apps/api/.env.demo, loaded by compose.demo.yaml as described in [the external services guide](../../EXTERNAL-SERVICES.md#4-store-the-database-secret-on-the-backend-laptop). Leave apps/api/.env and the original development Compose setup unchanged. DATABASE_URL_UNPOOLED is a proposed release/migration configuration convention; the current app does not consume it yet. Store it only in the controlled environment that will run migrations. For the optional hosted alternative, use a Fly app secret instead.

Do not put either URL in Vercel `NEXT_PUBLIC_` variables. The current simulated preview has no database connection. In a future integrated frontend, the browser uses the selected same-origin Next.js proxy, which forwards authorized requests to FastAPI; PostgreSQL remains server-side.

The Compose service uses its own local DATABASE_URL. Creating a Neon project does not switch local containers to Neon automatically, and normal local testing should retain its isolated databases.

## Verify

In Neon SQL Editor, select the intended demo branch/database and run:

```sql
SELECT current_database(), current_user, version();
```

This establishes console access only. After deploying the API, run the following inside that service's container shell, using its injected DATABASE_URL:

```sh
uv run --frozen python scripts/check_runtime.py --database
```

It should identify the intended database and complete the trivial CP-SAT smoke check. It does not validate a domain schema. If connection fails, check role/password, branch endpoint, database name, driver prefix, encoding and TLS settings. Do not print the secret URL while troubleshooting.

## Schema gate

PR #52 provides an Alembic environment and `0001_jobs_foundation`, which creates only the internal queue tables; see the [worker runbook](WORKER-QUEUE.md). No domain revisions or demo seed exist. Review and test migrations against a dedicated target before applying them; a jobs-only upgrade does not create a functioning application database.

For a later integrated release: test all required migrations against an isolated branch, supply the direct/unpooled URL as `DATABASE_URL` to the migration process, and apply the reviewed revisions once as a release step. The loader reads `DATABASE_URL`; it does not automatically select `DATABASE_URL_UNPOOLED`. Add and verify a dedicated demo seed only when domain persistence is implemented.

## Completion checklist

- [ ] Correct project, region, PostgreSQL version, branch and database recorded.
- [ ] Required Postgres service enabled; unrelated Neon services left disabled.
- [ ] Existing compute settings checked separately from defaults for new computes.
- [ ] Effective size, suspension behavior, restore window and usage limits recorded.
- [ ] Demo and dev endpoints separated, with role privileges and migration setup marked as pending or verified.
- [ ] Pooled runtime and direct migration connections distinguished.
- [ ] Server-side credential storage configured.
- [ ] SQL Editor and deployed API connection checks both pass.
- [ ] Schema/seed status recorded as pending or verified.
