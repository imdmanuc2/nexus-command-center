#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
BACKUP="${1:-}"

if [[ -z "$BACKUP" || ! -d "$BACKUP" ]]; then
  echo "Usage: $0 /path/to/backups/package-064-TIMESTAMP" >&2
  exit 1
fi

cp -a "$BACKUP/backend/services/operational_state_engine.py" "$ROOT/backend/services/operational_state_engine.py"
cp -a "$BACKUP/backend/services/topology_service.py" "$ROOT/backend/services/topology_service.py"
cp -a "$BACKUP/backend/services/seymour_pool_sync_service.py" "$ROOT/backend/services/seymour_pool_sync_service.py"
cp -a "$BACKUP/frontend/js/graph.js" "$ROOT/frontend/js/graph.js"
sudo systemctl restart nexus-api.service
echo "Rollback PASS"
