#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"; export PYTHONPATH="$ROOT"
python3 - <<'PY'
from backend.capabilities.registry import get_capability_registry
from pathlib import Path
assert get_capability_registry().describe()
assert Path('backend/db/migrations/020_live_operations_console.sql').exists()
print('Python imports and Package 029 baseline PASS')
PY
command -v psql >/dev/null
[[ -f backend/data/private/cmdb.env ]]
echo "Package 030 doctor passed."
