#!/usr/bin/env python3
from pathlib import Path
p=Path('backend/api/server.py');t=p.read_text()
imp='from backend.modules import platform_automation\n'
if imp not in t:
 for a in ('from backend.modules import platform_recommendations\n','from backend.modules import platform_context\n','from backend.modules import platform_alerts\n'):
  if a in t: t=t.replace(a,a+imp,1);break
 else: raise SystemExit('Could not find Platform module import anchor.')
for route,handler in [('"/api/platform/automation/actions"','platform_automation.actions'),('"/api/platform/automation/runs"','platform_automation.runs'),('"/api/platform/automation/summary"','platform_automation.summary')]:
 if route in t: continue
 for a in ('            "/api/platform/recommendations": platform_recommendations.recommendations,\n','            "/api/platform/context": platform_context.overview,\n'):
  if a in t: t=t.replace(a,a+f'            {route}: {handler},\n',1);break
 else: raise SystemExit(f'Could not add route {route}')
p.write_text(t);print('Registered Platform automation APIs.')
