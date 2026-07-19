#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
cd "$ROOT"
echo "== Typed capability registry =="
python3 - <<'PY'
from backend.capabilities.registry import get_capability_registry
r=get_capability_registry()
assert r.resolve('host.identity')
try:
    r.resolve('shell.execute')
except ValueError:
    pass
else:
    raise AssertionError('arbitrary shell capability unexpectedly allowed')
print('Typed allow-listed capabilities              PASS')
PY

echo
echo "== Secure transport registry =="
python3 - <<'PY'
from backend.transports.registry import get_transport_registry
assert get_transport_registry().describe() == ['local','ssh']
print('Internal local/SSH transports                 PASS')
PY

echo
echo "== Local typed capability execution =="
python3 - <<'PY'
from backend.executors.managed_host_executor import ManagedHostExecutor
run={
 'runId':'package-028-local-test','actionId':'host.identity',
 'entityType':'server','entityId':'package-028-verification',
 'requestedBy':'package-028-verify','approvedBy':None,'dryRun':False,
 'inputPayload':{'transport':'local','correlationId':'package-028-verification','parameters':{}}
}
result=ManagedHostExecutor().execute(run).to_dict()
assert result['status']=='completed', result
assert result['details']['execution']['hostKeyVerified'] is True
assert result['details']['execution']['exitCode']==0
print('Structured typed execution                    PASS')
PY

echo
echo "== Arbitrary command rejection =="
python3 - <<'PY'
from backend.executors.managed_host_executor import ManagedHostExecutor
run={'runId':'x','actionId':'host.identity','entityType':'server','entityId':'package-028-verification','inputPayload':{'transport':'local','correlationId':'x','command':'id','parameters':{}}}
try:
    ManagedHostExecutor().execute(run)
except ValueError as exc:
    assert 'Arbitrary command' in str(exc)
else:
    raise AssertionError('arbitrary command was accepted')
print('Arbitrary commands rejected                   PASS')
PY

echo
echo "== Redaction =="
python3 - <<'PY'
from backend.transports.redaction import redact_text
text=redact_text('token=abc123 rpcpassword=hunter2',['abc123'])
assert 'abc123' not in text and 'hunter2' not in text
print('Output and secret redaction                   PASS')
PY

echo
echo "== Migration =="
set -a; source backend/data/private/cmdb.env; set +a
export PGPASSWORD="$NEXUS_DB_PASSWORD"
psql -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME" -Atc "SELECT version FROM public.schema_migrations WHERE version='019'" | grep -qx 019
echo "Migration 019                               PASS"

echo "Package 028 verified."
