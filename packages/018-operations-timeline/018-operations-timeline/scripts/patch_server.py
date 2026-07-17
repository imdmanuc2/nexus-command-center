#!/usr/bin/env python3
from pathlib import Path
p=Path("backend/api/server.py")
t=p.read_text()
imp="from backend.modules import platform_timeline\n"
if imp not in t:
    for a in ("from backend.modules import platform_automation\n",
              "from backend.modules import platform_recommendations\n"):
        if a in t:
            t=t.replace(a,a+imp,1); break
    else: raise SystemExit("No Platform import anchor.")
routes=[
('"/api/platform/timeline"',"platform_timeline.timeline"),
('"/api/platform/timeline/latest"',"platform_timeline.latest"),
('"/api/platform/timeline/summary"',"platform_timeline.timeline_summary")]
for route,handler in routes:
    if route in t: continue
    for a in (
      '            "/api/platform/automation/actions": platform_automation.actions,\n',
      '            "/api/platform/recommendations": platform_recommendations.recommendations,\n'):
        if a in t:
            t=t.replace(a,a+f"            {route}: {handler},\n",1); break
    else: raise SystemExit(f"No route anchor for {route}")
p.write_text(t)
print("Registered Platform timeline APIs.")
