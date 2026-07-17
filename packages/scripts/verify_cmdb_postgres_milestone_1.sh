#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
cd "$PROJECT_ROOT"

python3 - <<'PY'
from backend.db.connection import healthcheck
from backend.db.repositories.asset_repository import count_assets, summary
print(healthcheck())
print("asset_count:", count_assets())
print("summary:", summary())
PY

curl -fsS http://127.0.0.1:8080/api/cmdb/assets \
  | jq '{status,source,count,assets:[.assets[]|{id,friendlyName,ip,assetType}]}'

curl -fsS http://127.0.0.1:8080/api/cmdb/summary | jq
