#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "$ROOT"

echo "Package 076 doctor"

test -f backend/core/asset_manager.py
test -f backend/db/repositories/asset_repository.py
test -f backend/db/repositories/relationship_repository.py
test -f backend/services/managed_host_discovery_service.py

/usr/bin/python3 - <<'PY'
from backend.db.repositories.asset_repository import list_assets
from backend.db.repositories.relationship_repository import list_relationships

assets = list_assets(limit=5000)
relationships = list_relationships()

assert isinstance(assets, list)
assert isinstance(relationships, list)

print("CMDB repository access: PASS")
print("assets:", len(assets))
print("relationships:", len(relationships))
PY

echo "Package 076 doctor: PASS"
