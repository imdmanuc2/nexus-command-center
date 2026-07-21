#!/usr/bin/env bash
set -euo pipefail
PKG="$(cd "$(dirname "$0")/.." && pwd)"; ROOT="$(cd "$PKG/../.." && pwd)"
set -a; [[ -f "$ROOT/backend/data/private/cmdb.env" ]] && source "$ROOT/backend/data/private/cmdb.env"; set +a
BACKUP="$ROOT/packages/backups/040-service-topology-business-services-$(date +%Y%m%d-%H%M%S)"; mkdir -p "$BACKUP"
for f in backend/api/server.py frontend/js/nav.js; do [[ -f "$ROOT/$f" ]] && cp --parents "$ROOT/$f" "$BACKUP/"; done
install -D -m 0644 "$PKG/backend/db/repositories/service_topology_repository.py" "$ROOT/backend/db/repositories/service_topology_repository.py"
install -D -m 0644 "$PKG/backend/services/service_topology_service.py" "$ROOT/backend/services/service_topology_service.py"
install -D -m 0644 "$PKG/backend/modules/platform_services.py" "$ROOT/backend/modules/platform_services.py"
install -D -m 0644 "$PKG/backend/api/server.py" "$ROOT/backend/api/server.py"
install -D -m 0644 "$PKG/frontend/service-topology.html" "$ROOT/frontend/service-topology.html"
install -D -m 0644 "$PKG/frontend/css/service-topology.css" "$ROOT/frontend/css/service-topology.css"
install -D -m 0644 "$PKG/frontend/js/service-topology.js" "$ROOT/frontend/js/service-topology.js"
install -D -m 0644 "$PKG/frontend/js/nav.js" "$ROOT/frontend/js/nav.js"
install -D -m 0644 "$PKG/backend/db/migrations/029_service_topology_business_services.sql" "$ROOT/backend/db/migrations/029_service_topology_business_services.sql"
PGPASSWORD="${NEXUS_DB_PASSWORD:?NEXUS_DB_PASSWORD missing}" psql -v ON_ERROR_STOP=1 -h "${NEXUS_DB_HOST:-127.0.0.1}" -p "${NEXUS_DB_PORT:-5432}" -U "${NEXUS_DB_USER:-nexus_app}" -d "${NEXUS_DB_NAME:-nexus_platform}" -f "$ROOT/backend/db/migrations/029_service_topology_business_services.sql"
sudo systemctl restart nexus-api.service
printf 'Package 040 installed.\nBackup: %s\n' "$BACKUP"
