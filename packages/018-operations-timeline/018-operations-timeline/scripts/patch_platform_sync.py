#!/usr/bin/env python3
from pathlib import Path
p=Path("backend/jobs/platform_sync_job.py")
t=p.read_text()
imp="from backend.services.timeline_service import build_timeline\n"
if imp not in t:
    anchors=[
      "from backend.services.automation_engine_service import process_queued_automations\n",
      "from backend.services.recommendation_engine_service import evaluate_recommendations\n"]
    for a in anchors:
        if a in t:
            t=t.replace(a,a+imp,1); break
    else: raise SystemExit("No sync import anchor.")
if "timeline = build_timeline()" not in t:
    a="    automation = process_queued_automations()\n"
    if a not in t: raise SystemExit("No automation call anchor.")
    t=t.replace(a,a+"\n    timeline = build_timeline()\n",1)
if '"timelineEngine": timeline' not in t:
    a='        "automationEngine": automation,\n'
    if a not in t: raise SystemExit("No automation result anchor.")
    t=t.replace(a,a+'        "timelineEngine": timeline,\n',1)
p.write_text(t)
print("Integrated timeline engine into one-minute sync.")
