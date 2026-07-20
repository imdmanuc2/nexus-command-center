#!/usr/bin/env bash
set -euo pipefail
PKG="$(cd "$(dirname "$0")/.." && pwd)"; ROOT="$(cd "$PKG/../.." && pwd)"
cd "$ROOT"; set -a; source backend/data/private/cmdb.env; set +a
cp -a "$PKG/backend/." backend/
cp -a "$PKG/frontend/." frontend/
PGPASSWORD="$NEXUS_DB_PASSWORD" psql -v ON_ERROR_STOP=1 -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME" -f backend/db/migrations/021_enterprise_playbook_engine.sql
export PYTHONPATH="$ROOT"
python3 - <<'PY'
from backend.services.playbook_engine_service import catalog_payload
p=catalog_payload(); print(f"Synchronized {p['count']} playbooks")
PY
if command -v systemctl >/dev/null && systemctl list-unit-files nexus-api.service >/dev/null 2>&1; then sudo systemctl restart nexus-api.service; fi
echo "Package 030 installed."
