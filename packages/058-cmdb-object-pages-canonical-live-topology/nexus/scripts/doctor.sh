#!/usr/bin/env bash
set -euo pipefail
REPO="${NEXUS_REPO:-$HOME/Projects/Seymour/nexus-command-center}"
for f in \
  backend/jobs/platform_sync_job.py \
  backend/services/topology_service.py \
  backend/services/cmdb_object_service.py \
  frontend/js/graph.js; do
  test -f "$REPO/$f" || { echo "FAIL: missing $f"; exit 1; }
  echo "PASS: $f"
done
python3 - <<'PY'
import json, urllib.request
for path in ("overview?window=5m", "workers?window=5m"):
    url=f"http://192.168.1.169:8561/api/v1/statistics/{path}"
    with urllib.request.urlopen(url, timeout=5) as r:
        data=json.load(r)
    assert data is not None
print("PASS: Seymour telemetry reachable")
PY
echo "Doctor PASS"
