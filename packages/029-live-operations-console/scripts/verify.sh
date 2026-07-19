#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

printf '== Operation session modules ==\n'
python3 - <<'PYCHECK'
from pathlib import Path

required = [
    'backend/db/repositories/operation_session_repository.py',
    'backend/services/operation_session_service.py',
    'backend/modules/platform_operation_sessions.py',
]
for path in required:
    assert Path(path).exists(), path
print('Structured operation sessions             PASS')
PYCHECK

printf '\n== API routes ==\n'
grep -q '/api/platform/operation-session' backend/api/server.py
echo 'Live console API routes                    PASS'

printf '\n== Operations drawer ==\n'
grep -q 'operationsConsoleDrawer' frontend/operations-center.html
grep -q 'pollOperationsConsole' frontend/js/operations-center.js
echo 'Operations console drawer                  PASS'

printf '\n== Database objects ==\n'
set -a
source backend/data/private/cmdb.env
set +a
export PGPASSWORD="$NEXUS_DB_PASSWORD"

readarray -t OBJECTS < <(
  psql -At \
    -h "$NEXUS_DB_HOST" \
    -p "$NEXUS_DB_PORT" \
    -U "$NEXUS_DB_USER" \
    -d "$NEXUS_DB_NAME" \
    -v ON_ERROR_STOP=1 \
    -c "SELECT
          COALESCE(to_regclass('nexus.operation_sessions')::text, ''),
          COALESCE(to_regclass('nexus.operation_session_events')::text, ''),
          COALESCE(to_regclass('nexus.idx_operation_session_events_session')::text, ''),
          COALESCE(to_regclass('nexus.idx_operation_sessions_updated')::text, '');"
)

IFS='|' read -r SESSION_TABLE EVENT_TABLE EVENT_INDEX SESSION_INDEX <<< "${OBJECTS[0]:-}"
[[ "$SESSION_TABLE" == "nexus.operation_sessions" ]]
echo 'Operation sessions table                  PASS'
[[ "$EVENT_TABLE" == "nexus.operation_session_events" ]]
echo 'Operation events table                    PASS'
[[ "$EVENT_INDEX" == "nexus.idx_operation_session_events_session" ]]
echo 'Operation events index                    PASS'
[[ "$SESSION_INDEX" == "nexus.idx_operation_sessions_updated" ]]
echo 'Operation sessions index                  PASS'

printf '\nPackage 029 verified.\n'
