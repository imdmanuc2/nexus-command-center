#!/usr/bin/env python3
from pathlib import Path
p=Path('backend/jobs/platform_sync_job.py');t=p.read_text()
imp='from backend.jobs.platform_resource_sync import synchronize_platform_resources\n'
a='from scripts.sync_platform_inventory import main as sync_inventory\n'
if imp not in t:
    if a not in t:raise SystemExit('sync import anchor missing')
    t=t.replace(a,a+imp,1)
if 'resources = synchronize_platform_resources(' not in t:
    old='    stale = reconcile_stale_state(\n        stale_seconds=stale_seconds,\n        dry_run=dry_run,\n    )\n'
    new='    resources = synchronize_platform_resources(\n        stale_seconds=stale_seconds,\n    )\n\n'+old
    if old not in t:raise SystemExit('stale anchor missing')
    t=t.replace(old,new,1)
if '"resourcePersistence": resources' not in t:
    t=t.replace('        "staleReconciliation": stale,\n','        "resourcePersistence": resources,\n        "staleReconciliation": stale,\n',1)
p.write_text(t);print('Integrated resource persistence into Platform sync.')
