#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
cd "$ROOT"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
printf '== Operation session modules ==\n'
python3 - <<'PYCHECK'
from pathlib import Path
for p in ['backend/db/repositories/operation_session_repository.py','backend/services/operation_session_service.py','backend/modules/platform_operation_sessions.py']:
    assert Path(p).exists(), p
print('Structured operation sessions             PASS')
PYCHECK
printf '\n== API routes ==\n'
grep -q '/api/platform/operation-session' backend/api/server.py && echo 'Live console API routes                    PASS'
printf '\n== Operations drawer ==\n'
grep -q 'operationsConsoleDrawer' frontend/operations-center.html
grep -q 'pollOperationsConsole' frontend/js/operations-center.js
echo 'Operations console drawer                  PASS'
printf '\n== Migration ==\n'
set -a; source backend/data/private/cmdb.env; set +a
export PGPASSWORD="$NEXUS_DB_PASSWORD"
FOUND="$(psql -At -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME" -c "SELECT COUNT(*) FROM nexus.schema_migrations WHERE version='020'")"
[[ "$FOUND" == "1" ]] && echo 'Migration 020                               PASS'
printf '\nPackage 029 verified.\n'
