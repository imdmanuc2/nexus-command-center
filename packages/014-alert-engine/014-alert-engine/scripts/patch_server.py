#!/usr/bin/env python3
from pathlib import Path

path = Path("backend/api/server.py")
text = path.read_text(encoding="utf-8")

import_line = "from backend.modules import platform_alerts\n"

if import_line not in text:
    for anchor in (
        "from backend.modules import platform_events\n",
        "from backend.modules import platform_miningcore\n",
        "from backend.modules import metrics\n",
    ):
        if anchor in text:
            text = text.replace(anchor, anchor + import_line, 1)
            break
    else:
        raise SystemExit("Could not find module import anchor.")

routes = [
    ('"/api/platform/alerts"', "platform_alerts.alerts"),
    ('"/api/platform/alerts/active"', "platform_alerts.active_alerts"),
    ('"/api/platform/alerts/summary"', "platform_alerts.summary"),
]

for route, handler in routes:
    if route in text:
        continue

    for anchor in (
        '            "/api/platform/events": platform_events.events,\n',
        '            "/api/platform/miningcore": platform_miningcore.instance_list,\n',
        '            "/api/platform/metrics": metrics.metrics_summary,\n',
    ):
        if anchor in text:
            text = text.replace(
                anchor,
                anchor + f"            {route}: {handler},\n",
                1,
            )
            break
    else:
        raise SystemExit(f"Could not add route {route}")

path.write_text(text, encoding="utf-8")
print("Registered Platform alert APIs.")
