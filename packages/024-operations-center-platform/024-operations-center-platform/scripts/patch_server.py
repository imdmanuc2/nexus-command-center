
#!/usr/bin/env python3

from pathlib import Path

path = Path("backend/api/server.py")
text = path.read_text(encoding="utf-8")

import_line = (
    "from backend.modules import "
    "platform_operations_center\n"
)

if import_line not in text:
    anchor = (
        "from backend.modules "
        "import platform_timeline\n"
    )

    if anchor not in text:
        raise SystemExit(
            "Could not find Platform module import anchor."
        )

    text = text.replace(
        anchor,
        anchor + import_line,
        1,
    )

routes = [
    (
        '"/api/platform/operations-center"',
        "platform_operations_center.dashboard",
    ),
    (
        '"/api/platform/operations-center/status"',
        "platform_operations_center.status",
    ),
    (
        '"/api/platform/operations-center/queue"',
        "platform_operations_center.queue",
    ),
    (
        '"/api/platform/operations-center/snapshot"',
        "platform_operations_center.snapshot",
    ),
]

anchor = (
    '            "/api/platform/timeline": '
    "platform_timeline.timeline,\n"
)

for route, handler in routes:
    if route in text:
        continue

    if anchor not in text:
        raise SystemExit(
            f"Could not add route {route}"
        )

    text = text.replace(
        anchor,
        anchor
        + f"            {route}: {handler},\n",
        1,
    )

path.write_text(
    text,
    encoding="utf-8",
)

print(
    "Registered Operations Center Platform APIs."
)
