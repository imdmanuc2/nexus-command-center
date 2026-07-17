
#!/usr/bin/env python3

from pathlib import Path

path = Path(
    "backend/jobs/platform_sync_job.py"
)
text = path.read_text(encoding="utf-8")

import_line = (
    "from backend.services."
    "operations_center_service "
    "import build_operations_center\n"
)

if import_line not in text:
    anchor = (
        "from backend.services."
        "timeline_service "
        "import build_timeline\n"
    )

    if anchor not in text:
        raise SystemExit(
            "Could not find sync import anchor."
        )

    text = text.replace(
        anchor,
        anchor + import_line,
        1,
    )

call = (
    "    operations_center = "
    "build_operations_center("
    "persist=True)\n"
)

if call not in text:
    anchor = (
        "    timeline = build_timeline()\n"
    )

    if anchor not in text:
        raise SystemExit(
            "Could not find timeline call anchor."
        )

    text = text.replace(
        anchor,
        anchor + "\n" + call,
        1,
    )

field = (
    '        "operationsCenter": '
    "operations_center,\n"
)

if field not in text:
    anchor = (
        '        "timelineEngine": '
        "timeline,\n"
    )

    if anchor not in text:
        raise SystemExit(
            "Could not find timeline result anchor."
        )

    text = text.replace(
        anchor,
        anchor + field,
        1,
    )

path.write_text(
    text,
    encoding="utf-8",
)

print(
    "Integrated Operations Center snapshot "
    "into Platform sync."
)
