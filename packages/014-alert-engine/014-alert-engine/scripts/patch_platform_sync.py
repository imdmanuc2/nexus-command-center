#!/usr/bin/env python3
from pathlib import Path

path = Path("backend/jobs/platform_sync_job.py")
text = path.read_text(encoding="utf-8")

import_line = (
    "from backend.services.alert_engine_service "
    "import evaluate_alerts\n"
)

if import_line not in text:
    for anchor in (
        "from backend.services.platform_event_service import evaluate_platform_state\n",
        "from backend.jobs.platform_resource_sync import synchronize_platform_resources\n",
    ):
        if anchor in text:
            text = text.replace(anchor, anchor + import_line, 1)
            break
    else:
        raise SystemExit("Could not find sync import anchor.")

if "alerts = evaluate_alerts()" not in text:
    anchor = "    events = evaluate_platform_state()\n"
    if anchor not in text:
        raise SystemExit("Could not find event engine call.")
    text = text.replace(
        anchor,
        anchor + "\n    alerts = evaluate_alerts()\n",
        1,
    )

if '"alertEngine": alerts' not in text:
    anchor = '        "eventEngine": events,\n'
    if anchor not in text:
        raise SystemExit("Could not find eventEngine result field.")
    text = text.replace(
        anchor,
        anchor + '        "alertEngine": alerts,\n',
        1,
    )

path.write_text(text, encoding="utf-8")
print("Integrated Platform alert engine into one-minute sync.")
