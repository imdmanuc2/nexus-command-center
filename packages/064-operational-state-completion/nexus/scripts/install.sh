#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
PAYLOAD="$SCRIPT_DIR/../payload"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$ROOT/backups/package-064-$STAMP"

mkdir -p "$BACKUP/backend/services" "$BACKUP/frontend/js"
for file in \
  backend/services/operational_state_engine.py \
  backend/services/topology_service.py \
  backend/services/seymour_pool_sync_service.py \
  frontend/js/graph.js; do
  cp -a "$ROOT/$file" "$BACKUP/$file"
done
echo "Backup: $BACKUP"

install -m 0644 "$PAYLOAD/backend/services/operational_state_engine.py" "$ROOT/backend/services/operational_state_engine.py"
install -m 0644 "$PAYLOAD/backend/services/topology_service.py" "$ROOT/backend/services/topology_service.py"
install -m 0644 "$PAYLOAD/backend/services/seymour_pool_sync_service.py" "$ROOT/backend/services/seymour_pool_sync_service.py"
install -m 0644 "$PAYLOAD/frontend/js/graph.js" "$ROOT/frontend/js/graph.js"

cd "$ROOT"
if [[ -f backend/data/private/cmdb.env ]]; then
  set -a
  # shellcheck disable=SC1091
  source backend/data/private/cmdb.env
  set +a
fi
/usr/bin/python3 -m backend.jobs.platform_sync_job >/tmp/package-064-sync.log 2>&1 || {
  cat /tmp/package-064-sync.log >&2
  exit 1
}
cat /tmp/package-064-sync.log

sudo systemctl restart nexus-api.service
for _ in $(seq 1 30); do
  if curl -fsS http://localhost:8080/api/platform/topology >/dev/null 2>&1; then
    echo "Install PASS"
    exit 0
  fi
  sleep 1
done

echo "FAIL: nexus-api.service did not become ready" >&2
exit 1
