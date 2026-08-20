#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
TARGET="$ROOT/backend/services/platform_inventory_service.py"
API="${NEXUS_API_URL:-http://127.0.0.1:8080}"

echo "===== PACKAGE 079 VERIFY ====="

grep -q 'from backend.db.repositories.asset_repository import list_assets' "$TARGET"
echo "PASS: asset repository imported"

grep -q 'assets = list_assets()' "$TARGET"
echo "PASS: canonical assets loaded"

grep -q '"assets": len(assets)' "$TARGET"
echo "PASS: canonical asset count projected"

grep -q '"assets": assets' "$TARGET"
echo "PASS: canonical assets projected"

python3 -m py_compile "$TARGET"
echo "PASS: platform inventory service compiles"

TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT

curl -fsS "$API/api/platform/inventory" > "$TMP"

python3 - "$TMP" <<'PY'
import json
import sys

with open(sys.argv[1]) as handle:
    data = json.load(handle)

assert data.get("status") == "ok", data
assert data.get("source") == "nexus-postgresql-platform", data

assets = data.get("assets")
assert isinstance(assets, list), "inventory.assets is not a list"
assert len(assets) > 0, "inventory.assets is empty"

counts = data.get("counts") or {}
assert counts.get("assets") == len(assets), (
    f"counts.assets={counts.get('assets')} "
    f"but len(assets)={len(assets)}"
)

required = {
    "assets",
    "pools",
    "workers",
    "workloads",
    "relationships",
}

missing = sorted(required - set(data))
assert not missing, f"missing inventory keys: {missing}"

ids = [asset.get("id") or asset.get("assetId") for asset in assets]
assert all(ids), f"one or more canonical assets lack identity: {ids}"

print(f"PASS: API returned {len(assets)} canonical assets")
print("Asset IDs:")
for asset_id in ids:
    print(f"  {asset_id}")
PY

echo "PACKAGE 079 VERIFY PASS"
