#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
TARGET="$ROOT/backend/services/platform_inventory_service.py"
BACKUP_DIR="$ROOT/backups"
STAMP="$(date -u +%Y%m%d-%H%M%S)"
BACKUP="$BACKUP_DIR/platform_inventory_service.py.before-079-$STAMP"

mkdir -p "$BACKUP_DIR"

echo "===== PACKAGE 079 INSTALL ====="

cp "$TARGET" "$BACKUP"
echo "Backup: $BACKUP"

python3 - "$TARGET" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text()

asset_import = "from backend.db.repositories.asset_repository import list_assets\n"

if asset_import not in text:
    marker = "from backend.db.repositories.pool_repository import list_pools\n"
    if marker not in text:
        raise SystemExit("ERROR: pool repository import marker not found")
    text = text.replace(marker, asset_import + marker, 1)

old = """def inventory() -> dict[str, Any]:
    pools = list_pools()
    workers = list_workers()
    workloads = list_workloads()
    relationships = list_relationships()

    return {
        "status": "ok",
        "source": "nexus-postgresql-platform",
        "counts": {
            "pools": len(pools),
            "workers": len(workers),
            "workloads": len(workloads),
            "relationships": len(relationships),
        },
        "pools": pools,
        "workers": workers,
        "workloads": workloads,
        "relationships": relationships,
    }
"""

new = """def inventory() -> dict[str, Any]:
    assets = list_assets()
    pools = list_pools()
    workers = list_workers()
    workloads = list_workloads()
    relationships = list_relationships()

    return {
        "status": "ok",
        "source": "nexus-postgresql-platform",
        "counts": {
            "assets": len(assets),
            "pools": len(pools),
            "workers": len(workers),
            "workloads": len(workloads),
            "relationships": len(relationships),
        },
        "assets": assets,
        "pools": pools,
        "workers": workers,
        "workloads": workloads,
        "relationships": relationships,
    }
"""

if old in text:
    text = text.replace(old, new, 1)
elif '"assets": assets,' in text and '"assets": len(assets)' in text:
    print("Package 079 inventory patch already present.")
else:
    raise SystemExit(
        "ERROR: expected inventory() block not found; "
        "refusing unsafe partial modification"
    )

path.write_text(text)
PY

python3 -m py_compile "$TARGET"

echo "PASS: canonical asset projection installed"
echo "Restart nexus-api.service before running verify.sh."
echo "PACKAGE 079 INSTALL PASS"
