#!/usr/bin/env bash
set -euo pipefail

PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(cd "$PKG_DIR/../.." && pwd)"

required=(
  "$ROOT/backend/data/private/cmdb.env"
  "$ROOT/backend/api/server.py"
  "$ROOT/backend/db/repositories/change_rollback_repository.py"
  "$ROOT/backend/services/change_rollback_service.py"
  "$ROOT/backend/modules/platform_change_rollback.py"
  "$ROOT/backend/jobs/change_rollback_worker.py"
  "$ROOT/backend/transports/target_resolver.py"
)

for path in "${required[@]}"; do
  test -f "$path" || {
    echo "Missing required file: $path" >&2
    exit 1
  }
done

command -v python3 >/dev/null
command -v psql >/dev/null
command -v curl >/dev/null
command -v systemctl >/dev/null

grep -q '"nexus-local"' "$ROOT/backend/transports/target_resolver.py" || {
  echo "Reserved local Nexus identity 'nexus-local' is not available." >&2
  exit 1
}

grep -q "def run_once" "$ROOT/backend/services/change_rollback_service.py"
grep -q "def claim_next" "$ROOT/backend/db/repositories/change_rollback_repository.py"

echo "Package 047 R4 doctor PASS"
