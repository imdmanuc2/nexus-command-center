#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
cd "$ROOT"
test -f backend/data/private/cmdb.env
test -f backend/api/server.py
test -f frontend/operations-center.html
set -a
source backend/data/private/cmdb.env
set +a
export PGPASSWORD="$NEXUS_DB_PASSWORD"
psql -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME" -v ON_ERROR_STOP=1 -Atc "SELECT to_regclass('nexus.automation_runs')" | grep -q automation_runs
curl --max-time 10 -fsS http://127.0.0.1:8080/api/platform/operations-center | jq -e '.status == "ok"' >/dev/null
echo "Package 026 doctor passed."
