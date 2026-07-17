#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
cd "$ROOT"
echo "== Event engine =="
python3 -m backend.jobs.platform_event_job
echo "== Alert engine =="
python3 -m backend.jobs.platform_alert_job
echo "== Context builder =="
python3 -m backend.jobs.platform_context_job
echo "== Integrated Platform sync =="
python3 - <<'PY'
import contextlib, io, json
from backend.jobs.platform_sync_job import run_once
captured = io.StringIO()
with contextlib.redirect_stdout(captured):
    result = run_once(stale_seconds=300, dry_run=False)
print(json.dumps({
    'status': result.get('status'),
    'eventEngine': result.get('eventEngine'),
    'alertEngine': result.get('alertEngine'),
    'contextBuilder': result.get('contextBuilder'),
    'recommendationEngine': result.get('recommendationEngine'),
    'automationEngine': result.get('automationEngine'),
    'timelineEngine': result.get('timelineEngine'),
}, indent=2))
PY
echo "== API health =="
for endpoint in \
  api/platform/events \
  api/platform/alerts \
  api/platform/context \
  api/platform/recommendations \
  api/platform/automation/summary \
  api/platform/timeline/latest
do
  printf '%-42s ' "/$endpoint"
  curl --max-time 10 -fsS "http://127.0.0.1:8080/$endpoint" >/dev/null && echo PASS || echo FAIL
done
echo "Package 021 verified."
