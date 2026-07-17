#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
cd "$PROJECT_ROOT"
mkdir -p backend/services backend/modules
for f in fleet_service.py worker_service.py pool_service.py workload_service.py relationship_service.py topology_service.py; do install -m 0644 "$PACKAGE_ROOT/backend/services/$f" "backend/services/$f"; done
install -m 0644 "$PACKAGE_ROOT/backend/modules/platform.py" backend/modules/platform.py
cp backend/api/server.py "backend/api/server.py.before-platform-services-$STAMP"
python3 - <<'PY2'
from pathlib import Path
p=Path('backend/api/server.py'); text=p.read_text()
if 'from backend.modules import platform
' not in text:
    anchor='from backend.modules import platform_inventory
' if 'from backend.modules import platform_inventory
' in text else 'from backend.modules import cmdb
'
    if anchor not in text: raise SystemExit('No import anchor')
    text=text.replace(anchor,anchor+'from backend.modules import platform
',1)
routes=[('"/api/platform/fleet"','platform.fleet_summary'),('"/api/platform/workers"','platform.worker_list'),('"/api/platform/pools"','platform.pool_list'),('"/api/platform/workloads"','platform.workload_list'),('"/api/platform/relationships"','platform.relationship_list'),('"/api/platform/topology"','platform.topology_graph')]
for route,handler in routes:
    if route in text: continue
    anchor='            "/api/platform/inventory": platform_inventory.summary,
' if '            "/api/platform/inventory": platform_inventory.summary,
' in text else '            "/api/cmdb/summary": cmdb.summary,
'
    if anchor not in text: raise SystemExit(f'No route anchor for {route}')
    text=text.replace(anchor,anchor+f'            {route}: {handler},
',1)
p.write_text(text)
PY2
python3 -m py_compile backend/services/*.py backend/modules/platform.py backend/api/server.py
echo 'Package 006 installed.'
