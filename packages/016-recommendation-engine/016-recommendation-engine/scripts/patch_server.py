#!/usr/bin/env python3
from pathlib import Path

path = Path("backend/api/server.py")
text = path.read_text(encoding="utf-8")

import_line = "from backend.modules import platform_recommendations\n"

if import_line not in text:
    for anchor in (
        "from backend.modules import platform_context\n",
        "from backend.modules import platform_alerts\n",
        "from backend.modules import platform_events\n",
    ):
        if anchor in text:
            text = text.replace(anchor, anchor + import_line, 1)
            break
    else:
        raise SystemExit("Could not find Platform module import anchor.")

routes = [
    (
        '"/api/platform/recommendations"',
        "platform_recommendations.recommendations",
    ),
    (
        '"/api/platform/recommendations/high-priority"',
        "platform_recommendations.high_priority",
    ),
    (
        '"/api/platform/recommendations/summary"',
        "platform_recommendations.summary",
    ),
]

for route, handler in routes:
    if route in text:
        continue

    for anchor in (
        '            "/api/platform/context": platform_context.overview,\n',
        '            "/api/platform/alerts": platform_alerts.alerts,\n',
        '            "/api/platform/events": platform_events.events,\n',
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
print("Registered Platform recommendation APIs.")
