#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
command -v python3 >/dev/null
command -v psql >/dev/null
test -f backend/db/connection.py
test -f backend/db/migrations/024_remote_deployments.sql
test -f backend/services/maintenance_service.py
python3 -m py_compile packages/036-asset-operational-state/backend/services/operational_state_service.py packages/036-asset-operational-state/backend/db/repositories/operational_state_repository.py packages/036-asset-operational-state/backend/api/server.py
echo "Package 036 doctor passed."
