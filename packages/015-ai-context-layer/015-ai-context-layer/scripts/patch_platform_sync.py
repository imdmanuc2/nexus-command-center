#!/usr/bin/env python3
from pathlib import Path

path = Path("backend/jobs/platform_sync_job.py")
text = path.read_text(encoding="utf-8")

import_line = (
    "from backend.services.platform_context_service "
    "import build_contexts\n"
)

if import_line not in text:
    for anchor in (
        "from backend.services.alert_engine_service import evaluate_alerts\n",
        "from backend.services.platform_event_service import evaluate_platform_state\n",
    ):
        if anchor in text:
            text = text.replace(anchor, anchor + import_line, 1)
            break
    else:
        raise SystemExit("Could not find Platform sync import anchor.")

if "context = build_contexts()" not in text:
    anchor = "    alerts = evaluate_alerts()\n"
    if anchor not in text:
        raise SystemExit("Could not find alert engine call.")
    text = text.replace(
        anchor,
        anchor + "\n    context = build_contexts()\n",
        1,
    )

if '"contextBuilder": context' not in text:
    anchor = '        "alertEngine": alerts,\n'
    if anchor not in text:
        raise SystemExit("Could not find alertEngine result field.")
    text = text.replace(
        anchor,
        anchor + '        "contextBuilder": context,\n',
        1,
    )

path.write_text(text, encoding="utf-8")
print("Integrated Platform context builder into one-minute sync.")
