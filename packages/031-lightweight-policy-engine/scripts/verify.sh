#!/usr/bin/env bash
set -euo pipefail
PKG="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$PKG/../.." && pwd)"
cd "$ROOT"
set -a
source backend/data/private/cmdb.env
set +a
export PYTHONPATH="$ROOT"
python3 -m py_compile \
  backend/policy/models.py backend/policy/engine.py \
  backend/db/repositories/policy_repository.py \
  backend/services/policy_engine_service.py \
  backend/modules/platform_policies.py backend/services/playbook_engine_service.py backend/api/server.py
python3 - <<'PY'
from backend.policy.engine import evaluate_operation
assert evaluate_operation('host.identity').decision == 'allow'
assert evaluate_operation('service.restart').decision == 'confirmation_required'
assert evaluate_operation('service.restart', confirmed=True).decision == 'allow'
assert evaluate_operation('shell.execute').decision == 'deny'
print('Policy evaluation PASS')
PY
PG="PGPASSWORD=$NEXUS_DB_PASSWORD psql -At -h $NEXUS_DB_HOST -p $NEXUS_DB_PORT -U $NEXUS_DB_USER -d $NEXUS_DB_NAME"
[ "$(eval "$PG -c \"SELECT to_regclass('nexus.execution_policies') IS NOT NULL\"")" = "t" ] && echo "execution_policies table PASS"
[ "$(eval "$PG -c \"SELECT to_regclass('nexus.policy_decisions') IS NOT NULL\"")" = "t" ] && echo "policy_decisions table PASS"
POLICY_COUNT=$(eval "$PG -c \"SELECT COUNT(*) FROM nexus.execution_policies WHERE enabled\"")
[ "$POLICY_COUNT" -ge 5 ] && echo "Default policy catalog PASS"
python3 - <<'PY'
from backend.services.policy_engine_service import evaluate_payload, policies_payload, decisions_payload
p=policies_payload(); assert p['count'] >= 5
result=evaluate_payload({'operation':'service.restart','requestedBy':'package-031-verifier'})
assert result['decision']=='confirmation_required'
result=evaluate_payload({'operation':'service.restart','requestedBy':'package-031-verifier','confirmed':True})
assert result['decision']=='allow'
assert decisions_payload(10)['count'] >= 2
print('Policy persistence and API service PASS')
PY
grep -q 'platform_policies' backend/api/server.py
grep -q '/api/policies/evaluate' backend/api/server.py
grep -q 'policy=evaluate_payload' backend/services/playbook_engine_service.py
echo "API routes and playbook integration PASS"
[ -f frontend/policies.html ] && [ -f frontend/js/policies.js ] && [ -f frontend/css/policies.css ]
echo "Policies UI PASS"
echo "Package 031 verified."
