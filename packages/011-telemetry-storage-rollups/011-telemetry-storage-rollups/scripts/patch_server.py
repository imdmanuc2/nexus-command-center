from pathlib import Path
p=Path("backend/api/server.py")
t=p.read_text()
line="from backend.modules import metrics\n"
if line not in t:
    for a in ("from backend.modules import platform\n","from backend.modules import platform_inventory\n","from backend.modules import cmdb\n"):
        if a in t:
            t=t.replace(a,a+line,1); break
    else: raise SystemExit("No import anchor")
routes=[('"/api/platform/metrics"',"metrics.metrics_summary"),
('"/api/platform/metrics/current"',"metrics.current_metrics"),
('"/api/platform/metrics/history"',"metrics.metric_history"),
('"/api/platform/metrics/rollups"',"metrics.metric_rollups")]
for route,handler in routes:
    if route in t: continue
    for a in ('            "/api/platform/workloads": platform.workload_list,\n',
              '            "/api/platform/fleet": platform.fleet_summary,\n',
              '            "/api/platform/inventory": platform_inventory.summary,\n'):
        if a in t:
            t=t.replace(a,a+f"            {route}: {handler},\n",1); break
    else: raise SystemExit(f"No route anchor for {route}")
p.write_text(t)
print("Registered Platform metrics API routes.")
