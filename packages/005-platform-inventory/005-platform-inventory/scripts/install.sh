#!/usr/bin/env bash
set -Eeuo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"

cd "$PROJECT_ROOT"

mkdir -p backend/db/repositories backend/services backend/modules

for file in   pool_repository.py   worker_repository.py   workload_repository.py   relationship_repository.py
do
  install -m 0644     "$PACKAGE_ROOT/backend/db/repositories/$file"     "backend/db/repositories/$file"
done

install -m 0644   "$PACKAGE_ROOT/backend/services/platform_inventory_service.py"   backend/services/platform_inventory_service.py

install -m 0644   "$PACKAGE_ROOT/backend/modules/platform_inventory.py"   backend/modules/platform_inventory.py

install -m 0755   "$PACKAGE_ROOT/scripts/sync_platform_inventory.py"   scripts/sync_platform_inventory.py

cp backend/api/server.py "backend/api/server.py.before-platform-inventory-$STAMP"

python3 - <<'PY'
from pathlib import Path

path = Path("backend/api/server.py")
text = path.read_text()

if "from backend.modules import platform_inventory" not in text:
    anchor = "from backend.modules import cmdb\n"
    if anchor not in text:
        raise SystemExit("Could not find CMDB module import anchor in server.py")
    text = text.replace(
        anchor,
        anchor + "from backend.modules import platform_inventory\n",
        1,
    )

if '"/api/platform/inventory"' not in text:
    candidates = [
        '            "/api/cmdb/summary": cmdb.summary,\n',
        '            "/api/cmdb/assets": cmdb.assets,\n',
    ]
    for anchor in candidates:
        if anchor in text:
            addition = (
                anchor
                + '            "/api/platform/inventory": platform_inventory.summary,\n'
                + '            "/api/platform/topology": platform_inventory.graph,\n'
            )
            text = text.replace(anchor, addition, 1)
            break
    else:
        raise SystemExit("Could not find route insertion anchor in server.py")

path.write_text(text)
print("Patched backend/api/server.py")
PY

python3 -m py_compile   backend/db/repositories/pool_repository.py   backend/db/repositories/worker_repository.py   backend/db/repositories/workload_repository.py   backend/db/repositories/relationship_repository.py   backend/services/platform_inventory_service.py   backend/modules/platform_inventory.py   scripts/sync_platform_inventory.py   backend/api/server.py

echo
echo "Package 005 installed."
echo "Next:"
echo "  sudo systemctl restart nexus-api.service"
echo "  python3 -m scripts.sync_platform_inventory"
