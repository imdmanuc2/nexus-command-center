#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
cd "$ROOT"

SERVICE="backend/services/blockchain_runtime_identity_consolidation_service.py"

echo "Package 078 doctor"

test -f "$SERVICE"
python3 -m py_compile "$SERVICE"

python3 - <<'PY'
from backend.db.repositories.asset_repository import count_assets
from backend.db.repositories.relationship_repository import list_relationships

assets = count_assets()
relationships = len(list_relationships())

print("CMDB repository access: PASS")
print(f"assets: {assets}")
print(f"relationships: {relationships}")
PY

echo "Package 078 doctor: PASS"
