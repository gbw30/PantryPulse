# W3 decisions: change requests and escalations from the wave-3 lanes

**Status:** decided by Gabriel, 2026-11-09. **Applies to:** the W3 lanes, W4 and W5. The lane status files (`docs/plans/v1/status/w3-*.md` on each `lane/w3-*` branch) hold each request in full.

## 1. CR-w3-samples-1: sample rates read "sample values" (approved, lead)

- **Change:** V1-SPEC §8 labels a sample network's pre-filled poverty and SNAP rates "sample values". `location_attributes` (`apps/api/app/services/enrichment/service.py`) now reports source "sample values" instead of "manual" when no rate comes from a lookup (each rate is manual or missing) and the location's network has `is_sample`. The state stays `manual`. The scenario freeze copies the source, so a frozen sample scenario carries the same label.
- **Test:** `test_sample_network_template_rates_labeled_sample_values`. A sample import reads "sample values"; the same files imported as a normal network read "manual".
- **Known limit:** no column tells a template rate apart from a user's own edit (`PUT .../attributes` writes the same `manual_*` columns). A user's edit on a sample location therefore also reads "sample values". Sample rates come pre-filled, so EGP never asks for one. If sample editing matters later, add a column that records who entered the rates.
- **Screen (web lane):** `attribute-editor.tsx` `sourceLine` shows "Source: entered by you" for every `manual` state and never reads `source`, so the label doesn't reach the screen yet. The web lane shows "Source: sample values" when `source` says so (verifier, 2026-11-09).

## 2. CR-w3-samples-2: template CSVs keep LF on Windows (approved, lead)

`.gitattributes` adds `data/templates/**/*.csv text eol=lf`. With `core.autocrlf=true`, a Windows checkout turned the templates into CRLF, so the byte-equality drift tests failed there. The importer already accepts CRLF.

## 3. CR-w3-web-1: the CI connected step runs the backend with no egress (approved, option (a), lead)

- **Why:** V1-A10 (enrichment offline → unknown, with retry) must be shown with an API that can't reach the internet. CI rejects skips, so the web lane's test fails unless `PP_E2E_NO_EGRESS=1` is set.
- **Change** (`.github/workflows/pantrypulse-ci.yml`):
  1. `sudo sysctl -w kernel.apparmor_restrict_unprivileged_userns=0`. GitHub's Ubuntu 24.04 image restricts unprivileged user namespaces.
  2. The API and the worker each run under `unshare -rn`. They reach PostgreSQL through a unix socket, and the API serves on one. `scripts/quality/netns-bridge.py` forwards both to TCP on the host.
  3. The step sets `PP_E2E_NO_EGRESS=1` and first checks that a connection from the namespace fails with `ENETUNREACH`.
- **Bridge:** `netns-bridge.py` is the web lane's `apps/web/tests/e2e/connected/bridge.py`, now lead-owned. After this merges, the web lane points `stack-up.sh` at it and deletes its own copy.
- **Rejected:** option (b), a separate worker user with an `iptables` owner rule. It needs more runner plumbing, and the lane hadn't tested it.

## 4. E-1: fixture forecast run in the web lane's connected journeys (approved)

The connected Pantry and Retail journeys need a forecast run to freeze a scenario. The network forecast routes stay 501 until W3-F03 merges. The web lane therefore seeds a fixture forecast run, the way `tests/integration/test_v1_backend_journey.py` does, and keeps the `?forecast_run_id=` stopgap. Import, scenario, comparison, decisions and export stay real. The PR discloses the fixture, and it never counts as forecast evidence. **W4-02** switches these journeys to a real `forecast.v1` run.

## 5. CR-w3-forecast-1: where backtest results are stored (open)

Filed at `lane/w3-forecast` `448f8e3`. `backtest_scores` (`ppv1_0008`) has no `origins_evaluated`, no pooled sums and no run key, so `get_backtest(job_id)` can't serve the CR-w1-web-4 contract.

| Option | Change |
|---|---|
| A | Widen `backtest_scores` with a run FK, `origins_evaluated`, the pooled sums and wider `wape`/`bias`. Reads aggregate up to 50k rows per request. |
| B (lane recommends) | A nullable `forecast_runs.backtest` JSONB column holding the `BacktestResult` body, written in the run's existing INSERT and read as one row. |

The lead lands either option as a migration. Until then, W3-F03 builds everything except `get_backtest`.
