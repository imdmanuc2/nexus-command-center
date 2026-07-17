#!/usr/bin/env python3
from pathlib import Path
p=Path('backend/jobs/platform_sync_job.py');t=p.read_text()
imp='from backend.services.automation_engine_service import process_queued_automations\n'
if imp not in t:
 for a in ('from backend.services.recommendation_engine_service import evaluate_recommendations\n','from backend.services.platform_context_service import build_contexts\n'):
  if a in t: t=t.replace(a,a+imp,1);break
 else: raise SystemExit('Could not find Platform sync import anchor.')
if 'automation = process_queued_automations()' not in t:
 a='    recommendations = evaluate_recommendations()\n'
 if a not in t: raise SystemExit('Could not find recommendation engine call.')
 t=t.replace(a,a+'\n    automation = process_queued_automations()\n',1)
if '"automationEngine": automation' not in t:
 a='        "recommendationEngine": recommendations,\n'
 if a not in t: raise SystemExit('Could not find recommendationEngine result field.')
 t=t.replace(a,a+'        "automationEngine": automation,\n',1)
p.write_text(t);print('Integrated automation engine into one-minute sync.')
