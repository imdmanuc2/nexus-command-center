#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO="${NEXUS_REPO:-$HOME/Projects/Seymour/nexus-command-center}"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$REPO/backups/package-058-$STAMP"
mkdir -p "$BACKUP"
FILES=(
  backend/services/seymour_pool_sync_service.py
  backend/services/cmdb_object_service.py
  backend/services/topology_service.py
  backend/jobs/platform_sync_job.py
  backend/data/config/seymour_pool_engine.json
  frontend/js/cmdb-object.js
  frontend/js/graph.js
  frontend/css/cmdb-object.css
)
for rel in "${FILES[@]}"; do
  if [ -f "$REPO/$rel" ]; then
    mkdir -p "$BACKUP/$(dirname "$rel")"
    cp -a "$REPO/$rel" "$BACKUP/$rel"
  fi
  src="$PKG_DIR/payload/$rel"
  test -f "$src" || { echo "FAIL: payload missing $rel"; exit 1; }
  mkdir -p "$REPO/$(dirname "$rel")"
  cp -a "$src" "$REPO/$rel"
done
printf '%s\n' "$BACKUP" > "$REPO/backups/package-058-latest"
cd "$REPO"
python3 -m py_compile \
  backend/services/seymour_pool_sync_service.py \
  backend/services/cmdb_object_service.py \
  backend/services/topology_service.py \
  backend/jobs/platform_sync_job.py
node --check frontend/js/graph.js
node --check frontend/js/cmdb-object.js
sudo systemctl restart nexus-api.service
sleep 2
systemctl is-active --quiet nexus-api.service
echo "Backup: $BACKUP"
echo "Install PASS"
