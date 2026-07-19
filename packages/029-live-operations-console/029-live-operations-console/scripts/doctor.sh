#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
python3 - <<'PYCHECK'
from pathlib import Path
required = [
 'backend/services/automation_engine_service.py',
 'backend/api/server.py',
 'frontend/operations-center.html',
 'frontend/js/operations-center.js',
 'frontend/css/operations-center.css',
 'backend/data/private/cmdb.env',
]
missing=[p for p in required if not Path(p).exists()]
if missing: raise SystemExit('Missing: '+', '.join(missing))
print('Package 029 doctor passed.')
PYCHECK
