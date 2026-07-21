#!/usr/bin/env bash
set -euo pipefail
PKG="$(cd "$(dirname "$0")/.." && pwd)"; ROOT="$(cd "$PKG/../.." && pwd)"
set -a; [[ -f "$ROOT/backend/data/private/cmdb.env" ]] && source "$ROOT/backend/data/private/cmdb.env"; set +a
BACKUP="$ROOT/packages/backups/039-dependency-impact-root-cause-analysis-$(date +%Y%m%d-%H%M%S)"; mkdir -p "$BACKUP"
for f in backend/api/server.py frontend/assets.html frontend/js/assets.js; do [[ -f "$ROOT/$f" ]] && cp --parents "$ROOT/$f" "$BACKUP/"; done
cp "$PKG/backend/core/impact_engine.py" "$ROOT/backend/core/"
cp "$PKG/backend/core/root_cause_engine.py" "$ROOT/backend/core/"
cp "$PKG/backend/core/recommendation_engine.py" "$ROOT/backend/core/"
cp "$PKG/backend/db/repositories/intelligence_repository.py" "$ROOT/backend/db/repositories/"
cp "$PKG/backend/services/intelligence_service.py" "$ROOT/backend/services/"
cp "$PKG/backend/modules/platform_intelligence.py" "$ROOT/backend/modules/"
cp "$PKG/backend/api/server.py" "$ROOT/backend/api/server.py"
cp "$PKG/frontend/assets.html" "$ROOT/frontend/assets.html"
cp "$PKG/frontend/js/assets.js" "$ROOT/frontend/js/assets.js"
cp "$PKG/frontend/css/intelligence.css" "$ROOT/frontend/css/intelligence.css"
cp "$PKG/backend/db/migrations/028_dependency_impact_root_cause_analysis.sql" "$ROOT/backend/db/migrations/"
PGPASSWORD="${NEXUS_DB_PASSWORD:?NEXUS_DB_PASSWORD missing}" psql -v ON_ERROR_STOP=1 -h "${NEXUS_DB_HOST:-127.0.0.1}" -p "${NEXUS_DB_PORT:-5432}" -U "${NEXUS_DB_USER:-nexus_app}" -d "${NEXUS_DB_NAME:-nexus_platform}" -f "$ROOT/backend/db/migrations/028_dependency_impact_root_cause_analysis.sql"
sudo systemctl restart nexus-api.service
printf 'Package 039 installed.\nBackup: %s\n' "$BACKUP"
