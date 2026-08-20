#!/usr/bin/env bash
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

echo "Package 077 doctor"

/usr/bin/python3 -m py_compile \
  backend/services/managed_host_storage_enrollment_service.py

/usr/bin/python3 - <<'PY'
from backend.core.asset_manager import (
    get_assets_list,
    upsert_managed_asset,
)
from backend.db.repositories.relationship_repository import (
    upsert_relationship,
)

assert callable(get_assets_list)
assert callable(upsert_managed_asset)
assert callable(upsert_relationship)

print("CMDB enrollment dependencies: PASS")
PY

echo "Package 077 doctor: PASS"
