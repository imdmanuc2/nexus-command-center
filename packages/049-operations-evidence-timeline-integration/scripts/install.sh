#!/usr/bin/env bash
set -euo pipefail
PACKAGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$PACKAGE_DIR/../.." && pwd)"
cd "$REPO_ROOT"
set -a
source backend/data/private/cmdb.env
set +a
export PGPASSWORD="${NEXUS_DB_PASSWORD:-}"
psql -h "${NEXUS_DB_HOST:-localhost}" -p "${NEXUS_DB_PORT:-5432}" -U "${NEXUS_DB_USER:-nexus_app}" -d "${NEXUS_DB_NAME:-nexus_platform}" -v ON_ERROR_STOP=1 -f "$PACKAGE_DIR/backend/db/migrations/038_operations_evidence_timeline.sql"
install -D -m 0644 "$PACKAGE_DIR/backend/db/repositories/operation_evidence_repository.py" backend/db/repositories/operation_evidence_repository.py
install -D -m 0644 "$PACKAGE_DIR/backend/services/operation_evidence_service.py" backend/services/operation_evidence_service.py
install -D -m 0644 "$PACKAGE_DIR/backend/modules/platform_evidence.py" backend/modules/platform_evidence.py
install -D -m 0644 "$PACKAGE_DIR/backend/jobs/operation_evidence_worker.py" backend/jobs/operation_evidence_worker.py
/usr/bin/python3 "$PACKAGE_DIR/backend/api/patch_evidence_routes.py"
sudo install -m 0644 "$PACKAGE_DIR/systemd/nexus-operation-evidence-worker.service" /etc/systemd/system/nexus-operation-evidence-worker.service
sudo systemctl daemon-reload
sudo systemctl enable nexus-operation-evidence-worker.service
sudo systemctl restart nexus-operation-evidence-worker.service
sudo systemctl restart nexus-api.service
sleep 2
echo 'Package 049 install PASS'
