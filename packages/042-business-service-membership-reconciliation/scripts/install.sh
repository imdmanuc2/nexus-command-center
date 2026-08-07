#!/usr/bin/env bash
set -euo pipefail
PKG="$(cd "$(dirname "$0")/.." && pwd)"; ROOT="$(cd "$PKG/../.." && pwd)"
set -a; source "$ROOT/backend/data/private/cmdb.env"; set +a
BACKUP="$ROOT/packages/backups/042-business-service-membership-reconciliation-$(date +%Y%m%d-%H%M%S)"; mkdir -p "$BACKUP"
FILES=(backend/db/repositories/service_membership_repository.py backend/db/repositories/service_topology_repository.py backend/services/service_membership_service.py backend/services/service_topology_service.py backend/services/service_operations_service.py backend/modules/platform_service_membership.py backend/api/server.py frontend/service-operations.html frontend/css/service-operations.css frontend/js/service-operations.js backend/db/migrations/031_business_service_membership_reconciliation.sql)
for f in "${FILES[@]}"; do [[ -f "$ROOT/$f" ]] && cp --parents "$ROOT/$f" "$BACKUP/"; install -D -m 0644 "$PKG/$f" "$ROOT/$f"; done
PGPASSWORD="${NEXUS_DB_PASSWORD:?}" psql -v ON_ERROR_STOP=1 -h "${NEXUS_DB_HOST:-127.0.0.1}" -p "${NEXUS_DB_PORT:-5432}" -U "${NEXUS_DB_USER:-nexus_app}" -d "${NEXUS_DB_NAME:-nexus_platform}" -f "$ROOT/backend/db/migrations/031_business_service_membership_reconciliation.sql"
python3 -m py_compile "$ROOT/backend/db/repositories/service_membership_repository.py" "$ROOT/backend/db/repositories/service_topology_repository.py" "$ROOT/backend/services/service_membership_service.py" "$ROOT/backend/services/service_topology_service.py" "$ROOT/backend/services/service_operations_service.py" "$ROOT/backend/modules/platform_service_membership.py" "$ROOT/backend/api/server.py"
sudo systemctl restart nexus-api.service
for i in {1..15}; do curl -fsS http://127.0.0.1:8080/api/health >/dev/null && break; sleep 1; done
curl -fsS -X POST -H 'Content-Type: application/json' -d '{"triggerSource":"package-install"}' http://127.0.0.1:8080/api/services/membership/reconcile >/dev/null
printf 'Package 042 installed.\nBackup: %s\n' "$BACKUP"
