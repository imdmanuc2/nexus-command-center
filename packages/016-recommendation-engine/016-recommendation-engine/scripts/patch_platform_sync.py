#!/usr/bin/env python3
from pathlib import Path

path = Path("backend/jobs/platform_sync_job.py")
text = path.read_text(encoding="utf-8")

import_line = (
    "from backend.services.recommendation_engine_service "
    "import evaluate_recommendations\n"
)

if import_line not in text:
    for anchor in (
        "from backend.services.platform_context_service import build_contexts\n",
        "from backend.services.alert_engine_service import evaluate_alerts\n",
    ):
        if anchor in text:
            text = text.replace(anchor, anchor + import_line, 1)
            break
    else:
        raise SystemExit("Could not find Platform sync import anchor.")

if "recommendations = evaluate_recommendations()" not in text:
    anchor = "    context = build_contexts()\n"
    if anchor not in text:
        raise SystemExit("Could not find context builder call.")
    text = text.replace(
        anchor,
        anchor + "\n    recommendations = evaluate_recommendations()\n",
        1,
    )

if '"recommendationEngine": recommendations' not in text:
    anchor = '        "contextBuilder": context,\n'
    if anchor not in text:
        raise SystemExit("Could not find contextBuilder result field.")
    text = text.replace(
        anchor,
        anchor + '        "recommendationEngine": recommendations,\n',
        1,
    )

path.write_text(text, encoding="utf-8")
print("Integrated recommendation engine into one-minute sync.")
