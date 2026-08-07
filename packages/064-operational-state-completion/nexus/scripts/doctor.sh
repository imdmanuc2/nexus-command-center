#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
PAYLOAD="$SCRIPT_DIR/../payload"

for file in \
  backend/services/operational_state_engine.py \
  backend/services/topology_service.py \
  backend/services/seymour_pool_sync_service.py \
  frontend/js/graph.js; do
  test -f "$ROOT/$file" || { echo "FAIL: $file" >&2; exit 1; }
  test -f "$PAYLOAD/$file" || { echo "FAIL: payload/$file" >&2; exit 1; }
  echo "PASS: $file"
done

python3 -m py_compile \
  "$PAYLOAD/backend/services/operational_state_engine.py" \
  "$PAYLOAD/backend/services/topology_service.py" \
  "$PAYLOAD/backend/services/seymour_pool_sync_service.py"
node --check "$PAYLOAD/frontend/js/graph.js"

curl -fsS 'http://192.168.1.169:8561/api/v1/statistics/overview?window=5m' >/dev/null
echo "PASS: Seymour telemetry reachable"
echo "Doctor PASS"
