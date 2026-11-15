#!/usr/bin/env bash
# The lane's connected stack, mirroring the CI connected step (.github/workflows/pantrypulse-ci.yml:86-108):
# a NEW ppor_demo_* schema in the lane test database, generated presenter credentials (never eval'd),
# the API on 127.0.0.1:$PP_API_PORT (.env.lane) and the production-registry worker. Both API and worker run in their own
# network namespace (unshare -rn) with NO egress; they reach PostgreSQL through a unix-socket bridge,
# and the host reaches the API through a tcp->unix bridge on $PP_API_PORT.
# Usage: RUN=<short dir> stack-up.sh (AF_UNIX paths are capped at 107 bytes)   (stop with stack-down.sh)
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../../../../.." && pwd)
RUN=${RUN:?set RUN to a fresh run directory}
PY=$ROOT/apps/api/.venv/bin/python
cd "$ROOT"
set -a; . ./.env.lane; set +a
mkdir -p "$RUN/pg" "$RUN/imports"; chmod 700 "$RUN"
SCHEMA=ppor_demo_${COMPOSE_PROJECT_NAME//[^a-z0-9]/}_$(date +%m%d%H%M%S)
export DATABASE_URL_UNPOOLED="$PP_TEST_DATABASE_URL"
"$PY" apps/api/scripts/load_optimization_demo.py --schema "$SCHEMA" --output "$RUN/demo.json"
umask 077
"$PY" scripts/quality/demo-ci-env.py "$RUN/demo.json" > "$RUN/demo.env"  # holds '$': never eval
echo "$SCHEMA" > "$RUN/schema"
PG_PORT=$("$PY" -c 'import os; from sqlalchemy.engine import make_url; print(make_url(os.environ["PP_TEST_DATABASE_URL"]).port or 5432)')
"$PY" - "$RUN/pg" > "$RUN/netns-db-url" <<'PY'
import os, sys
from sqlalchemy.engine import make_url
u = make_url(os.environ["PP_TEST_DATABASE_URL"])
print(u.set(host=None, port=None, query={**u.query, "host": sys.argv[1], "port": str(u.port or 5432)})
      .render_as_string(hide_password=False))
PY
PG_HOST=$("$PY" -c 'import os; from sqlalchemy.engine import make_url; print(make_url(os.environ["PP_TEST_DATABASE_URL"]).host)')
: > "$RUN/pids"
"$PY" scripts/quality/netns-bridge.py "unix:$RUN/pg/.s.PGSQL.$PG_PORT" "tcp:$PG_HOST:$PG_PORT" > "$RUN/bridge-pg.log" 2>&1 &
echo $! >> "$RUN/pids"
"$PY" scripts/quality/netns-bridge.py "tcp:127.0.0.1:$PP_API_PORT" "unix:$RUN/api.sock" > "$RUN/bridge-api.log" 2>&1 &
echo $! >> "$RUN/pids"
# Wait for the PG bridge socket, as the CI connected step does.
for _ in $(seq 100); do [ -S "$RUN/pg/.s.PGSQL.$PG_PORT" ] && break; sleep 0.1; done

backend_env() {
  while IFS='=' read -r k v; do export "$k=$v"; done < "$RUN/demo.env"
  export DATABASE_URL="$(cat "$RUN/netns-db-url")" PP_DATABASE_SCHEMA="$SCHEMA" \
    PP_ALLOWED_ORIGINS=http://127.0.0.1:$PLAYWRIGHT_PORT PP_COOKIE_SECURE=false PP_IMPORT_DIR="$RUN/imports"
}
( backend_env; cd apps/api; exec unshare -rn .venv/bin/python -m uvicorn app.main:app --uds "$RUN/api.sock" ) > "$RUN/api.log" 2>&1 &
echo $! >> "$RUN/pids"
( backend_env; cd apps/api; exec unshare -rn .venv/bin/python -m app.workers.supervisor --registry production --schema "$SCHEMA" ) > "$RUN/worker.log" 2>&1 &
echo $! >> "$RUN/pids"

DATABASE_URL="$PP_TEST_DATABASE_URL" PP_DATABASE_SCHEMA="$SCHEMA" PANTRYPULSE_API_ORIGIN=http://127.0.0.1:$PP_API_PORT \
  "$PY" scripts/quality/wait-demo.py
echo "connected stack up: schema $SCHEMA, run dir $RUN"
