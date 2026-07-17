#!/usr/bin/env python3
from pathlib import Path
p=Path('backend/api/server.py');t=p.read_text()
for line in ['from backend.modules import platform_nodes\n','from backend.modules import platform_miningcore\n']:
    if line not in t:
        for a in ['from backend.modules import platform\n','from backend.modules import metrics\n','from backend.modules import platform_inventory\n']:
            if a in t:t=t.replace(a,a+line,1);break
        else:raise SystemExit('import anchor missing')
for route,handler in [('"/api/platform/nodes"','platform_nodes.node_list'),('"/api/platform/miningcore"','platform_miningcore.instance_list')]:
    if route not in t:
        for a in ['            "/api/platform/metrics": metrics.metrics_summary,\n','            "/api/platform/fleet": platform.fleet_summary,\n','            "/api/platform/inventory": platform_inventory.summary,\n']:
            if a in t:t=t.replace(a,a+f'            {route}: {handler},\n',1);break
        else:raise SystemExit('route anchor missing')
p.write_text(t);print('Registered Platform resource APIs.')
