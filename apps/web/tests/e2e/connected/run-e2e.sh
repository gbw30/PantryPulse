#!/usr/bin/env bash
# Run Playwright against the lane's connected stack. Usage: RUN=<dir> run-e2e.sh <playwright args...>
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../../../.." && pwd)
RUN=${RUN:?}
cd "$ROOT"
set -a; . ./.env.lane; set +a  # PLAYWRIGHT_PORT and PP_API_PORT are the lane's (plan README, isolation table)
# Connected runs never reuse a server (playwright.config.ts): one already on the port is a leftover with a stale build.
if (exec 3<>"/dev/tcp/127.0.0.1/${PLAYWRIGHT_PORT:?set PLAYWRIGHT_PORT in .env.lane}") 2>/dev/null; then
  echo "run-e2e.sh: port $PLAYWRIGHT_PORT is already in use (PLAYWRIGHT_PORT, .env.lane). Stop the server on it and run again." >&2
  exit 1
fi
while IFS='=' read -r k v; do export "$k=$v"; done < "$RUN/demo.env"
# stack-up.sh runs the API and worker in network namespaces with no egress.
export PP_E2E_NO_EGRESS=1 PP_RUN_CONNECTED=1 PANTRYPULSE_API_ORIGIN=http://127.0.0.1:$PP_API_PORT NEXT_TELEMETRY_DISABLED=1
# The seed-forecast helper reaches PostgreSQL directly (host side), like the CI step's env.
export DATABASE_URL="$PP_TEST_DATABASE_URL" PP_DATABASE_SCHEMA="$(cat "$RUN/schema")"
cd apps/web
exec npx playwright test "$@"
