#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO="${NEXUS_REPO:-$HOME/Projects/Seymour/nexus-command-center}"

required_repo_files=(
  backend/api/server.py
  backend/modules/platform.py
  backend/services/relationship_service.py
  backend/db/repositories/asset_repository.py
  backend/db/repositories/pool_repository.py
  backend/db/repositories/worker_repository.py
  backend/db/repositories/workload_repository.py
  frontend/assets.html
  frontend/js/assets.js
  frontend/css/style.css
)

required_payload_files=(
  backend/services/cmdb_object_service.py
  backend/services/relationship_service.py
  backend/modules/platform.py
  backend/api/server.py
  frontend/cmdb-object.html
  frontend/js/cmdb-object.js
  frontend/js/assets.js
  frontend/css/cmdb-object.css
  frontend/css/style.css
)

for file in "${required_repo_files[@]}"; do
  test -f "$REPO/$file" || { echo "FAIL: missing repository file $file"; exit 1; }
  echo "PASS: $file"
done

for file in "${required_payload_files[@]}"; do
  test -f "$PACKAGE_DIR/payload/$file" || { echo "FAIL: missing payload file $file"; exit 1; }
done

authoritative_count="$(curl -fsS http://127.0.0.1:8080/api/platform/inventory | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("count", len(d.get("assets", []))))' 2>/dev/null || echo 0)"
echo "PASS: platform inventory reachable ($authoritative_count records)"

echo "Doctor PASS"
