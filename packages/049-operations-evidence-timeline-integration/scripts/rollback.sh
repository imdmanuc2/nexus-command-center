#!/usr/bin/env bash
set -euo pipefail
PACKAGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$PACKAGE_DIR/../.." && pwd)"
cd "$REPO_ROOT"
sudo systemctl disable --now nexus-operation-evidence-worker.service 2>/dev/null || true
sudo rm -f /etc/systemd/system/nexus-operation-evidence-worker.service
sudo systemctl daemon-reload
if [[ -f backend/api/server.py.before-package-049 ]]; then
  cp backend/api/server.py.before-package-049 backend/api/server.py
  sudo systemctl restart nexus-api.service
fi
rm -f backend/db/repositories/operation_evidence_repository.py backend/services/operation_evidence_service.py backend/modules/platform_evidence.py backend/jobs/operation_evidence_worker.py
if [[ "${DROP_PACKAGE_049_DATA:-0}" == '1' ]]; then
  set -a; source backend/data/private/cmdb.env; set +a
  export PGPASSWORD="${NEXUS_DB_PASSWORD:-}"
  psql -h "${NEXUS_DB_HOST:-localhost}" -p "${NEXUS_DB_PORT:-5432}" -U "${NEXUS_DB_USER:-nexus_app}" -d "${NEXUS_DB_NAME:-nexus_platform}" -v ON_ERROR_STOP=1 <<'SQL'
BEGIN;
DROP TABLE IF EXISTS operation_annotations;
DROP TABLE IF EXISTS operation_evidence_events;
DROP TABLE IF EXISTS operation_evidence;
DROP TABLE IF EXISTS operation_evidence_worker_state;
COMMIT;
SQL
fi
echo 'Package 049 rollback PASS'
