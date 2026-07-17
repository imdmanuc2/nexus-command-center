#!/usr/bin/env bash
set -Eeuo pipefail
cd "${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
python3 - <<'PY'
from backend.core.cmdb_audit import summary
from backend.core.observation_engine import read_observations
print("audit:", summary())
print("observations:", len(read_observations(limit=5000)))
PY
curl -fsS http://127.0.0.1:8080/api/cmdb/audit | jq '{status,source,count}'
curl -fsS http://127.0.0.1:8080/api/cmdb/summary | jq '.audit'
