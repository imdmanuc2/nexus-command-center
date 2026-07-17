#!/usr/bin/env python3
from pathlib import Path

path = Path("backend/api/server.py")
text = path.read_text(encoding="utf-8")

import_line = "from backend.modules import platform\n"
if import_line not in text:
    for anchor in (
        "from backend.modules import platform_inventory\n",
        "from backend.modules import cmdb\n",
    ):
        if anchor in text:
            text = text.replace(anchor, anchor + import_line, 1)
            break
    else:
        raise SystemExit("Could not find module import anchor in server.py")

routes = [
    ('"/api/platform/fleet"', "platform.fleet_summary"),
    ('"/api/platform/workers"', "platform.worker_list"),
    ('"/api/platform/pools"', "platform.pool_list"),
    ('"/api/platform/workloads"', "platform.workload_list"),
    ('"/api/platform/relationships"', "platform.relationship_list"),
    ('"/api/platform/topology"', "platform.topology_graph"),
]

for route, handler in routes:
    if route in text:
        continue
    for anchor in (
        '            "/api/platform/inventory": platform_inventory.summary,\n',
        '            "/api/cmdb/summary": cmdb.summary,\n',
    ):
        if anchor in text:
            text = text.replace(anchor, anchor + f"            {route}: {handler},\n", 1)
            break
    else:
        raise SystemExit(f"Could not add route {route}")

path.write_text(text, encoding="utf-8")
print("Patched backend/api/server.py")
