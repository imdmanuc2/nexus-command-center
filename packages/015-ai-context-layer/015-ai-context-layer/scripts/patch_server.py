#!/usr/bin/env python3
from pathlib import Path

path = Path("backend/api/server.py")
text = path.read_text(encoding="utf-8")

import_line = "from backend.modules import platform_context\n"

if import_line not in text:
    for anchor in (
        "from backend.modules import platform_alerts\n",
        "from backend.modules import platform_events\n",
        "from backend.modules import metrics\n",
    ):
        if anchor in text:
            text = text.replace(anchor, anchor + import_line, 1)
            break
    else:
        raise SystemExit("Could not find Platform import anchor.")

routes = [
    ('"/api/platform/context"', "platform_context.overview"),
    ('"/api/platform/context/home"', "platform_context.home"),
    ('"/api/platform/context/mining"', "platform_context.mining"),
    (
        '"/api/platform/context/infrastructure"',
        "platform_context.infrastructure",
    ),
    ('"/api/platform/context/health"', "platform_context.health"),
]

for route, handler in routes:
    if route in text:
        continue

    for anchor in (
        '            "/api/platform/alerts": platform_alerts.alerts,\n',
        '            "/api/platform/events": platform_events.events,\n',
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
print("Registered Platform context APIs.")
