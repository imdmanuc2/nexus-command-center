#!/usr/bin/env bash
set -euo pipefail
PKG="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$PKG/../.." && pwd)"
cd "$ROOT"
export PYTHONPATH="$ROOT"
command -v python3 >/dev/null
command -v psql >/dev/null
[ -f backend/services/playbook_engine_service.py ]
[ -f backend/db/migrations/021_enterprise_playbook_engine.sql ]
python3 - <<'PY'
from backend.services.playbook_engine_service import catalog_payload
from backend.policy.engine import evaluate_operation
assert catalog_payload()['count'] >= 1
assert evaluate_operation('service.restart').decision == 'confirmation_required'
assert evaluate_operation('service.restart', confirmed=True).decision == 'allow'
assert evaluate_operation('shell.execute').decision == 'deny'
print('Python imports and Package 030 baseline PASS')
PY
echo "Package 031 doctor passed."
