#!/usr/bin/env bash
set -euo pipefail
PKG="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$PKG/../.." && pwd)"
cd "$ROOT"
set -a
source backend/data/private/cmdb.env
set +a
cp -a "$PKG/backend/." backend/
cp -a "$PKG/frontend/." frontend/
PGPASSWORD="$NEXUS_DB_PASSWORD" psql -v ON_ERROR_STOP=1 \
  -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME" \
  -f backend/db/migrations/022_lightweight_policy_engine.sql
export PYTHONPATH="$ROOT"
python3 - <<'PY'
from backend.db.repositories.policy_repository import sync_default_policies
print(f"Synchronized {sync_default_policies()} policies")
PY
if command -v systemctl >/dev/null && systemctl list-unit-files nexus-api.service >/dev/null 2>&1; then
  sudo systemctl restart nexus-api.service
fi
echo "Package 031 installed."
