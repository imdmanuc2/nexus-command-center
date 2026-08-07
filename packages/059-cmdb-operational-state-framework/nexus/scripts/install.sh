#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO="${NEXUS_REPO:-$HOME/Projects/Seymour/nexus-command-center}"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$REPO/backups/package-059-$STAMP"
mkdir -p "$BACKUP"
FILES=(
 backend/api/server.py
 backend/db/repositories/asset_repository.py
 backend/services/cmdb_object_service.py
 frontend/cmdb-object.html
 frontend/js/cmdb-object.js
 frontend/js/graph.js
 frontend/css/cmdb-object.css
)
cd "$REPO"
for f in "${FILES[@]}"; do
  if [ -f "$f" ]; then mkdir -p "$BACKUP/$(dirname "$f")"; cp -a "$f" "$BACKUP/$f"; fi
done
for f in "${FILES[@]}"; do
  mkdir -p "$(dirname "$f")"
  cp -a "$PKG_DIR/payload/$f" "$f"
done
for f in \
 backend/modules/platform_operational_profile.py \
 backend/services/operational_profile_service.py \
 backend/db/repositories/operational_profile_repository.py \
 backend/db/migrations/038_cmdb_operational_profile.sql; do
  mkdir -p "$(dirname "$f")"
  cp -a "$PKG_DIR/payload/$f" "$f"
done
set -a
source backend/data/private/cmdb.env
set +a
PGPASSWORD="$NEXUS_DB_PASSWORD" psql \
  -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" \
  -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME" \
  -v ON_ERROR_STOP=1 \
  -f backend/db/migrations/038_cmdb_operational_profile.sql >/dev/null
python3 -m py_compile \
 backend/api/server.py \
 backend/db/repositories/asset_repository.py \
 backend/db/repositories/operational_profile_repository.py \
 backend/services/operational_profile_service.py \
 backend/services/cmdb_object_service.py
sudo systemctl restart nexus-api.service
sleep 2
systemctl is-active --quiet nexus-api.service
echo "$BACKUP" > "$REPO/backups/package-059-latest"
echo "Backup: $BACKUP"
echo "Install PASS"
