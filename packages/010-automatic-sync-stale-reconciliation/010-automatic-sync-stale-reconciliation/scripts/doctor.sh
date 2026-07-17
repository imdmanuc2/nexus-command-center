#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
BASE="${BASE:-http://127.0.0.1:8080}"

cd "$PROJECT_ROOT"

test -f scripts/sync_platform_inventory.py
test -f backend/db/connection.py
test -f backend/db/repositories/worker_repository.py
test -f backend/db/repositories/pool_repository.py
test -f backend/db/repositories/workload_repository.py
test -f backend/db/repositories/relationship_repository.py

python3 - <<'PY'
from backend.db.connection import healthcheck
result = healthcheck()
assert result["status"] == "ok", result
print(result)
PY

curl -fsS "$BASE/api/platform/topology" \
  | jq -e '.status == "ok"' >/dev/null

echo "Package 010 doctor passed."
