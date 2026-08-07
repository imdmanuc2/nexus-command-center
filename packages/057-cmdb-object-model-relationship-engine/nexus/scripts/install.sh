#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO="${NEXUS_REPO:-$HOME/Projects/Seymour/nexus-command-center}"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$REPO/backups/package-057-$STAMP"

mkdir -p "$BACKUP_DIR"

files=(
  backend/api/server.py
  backend/modules/platform.py
  backend/services/relationship_service.py
  frontend/assets.html
  frontend/js/assets.js
  frontend/css/style.css
)

for file in "${files[@]}"; do
  mkdir -p "$BACKUP_DIR/$(dirname "$file")"
  cp "$REPO/$file" "$BACKUP_DIR/$file"
done

mkdir -p "$BACKUP_DIR/manifest"
printf '%s\n' "$BACKUP_DIR" > "$REPO/.package-057-last-backup"

cd "$PACKAGE_DIR/payload"
find backend frontend -type f -print0 | while IFS= read -r -d '' file; do
  mkdir -p "$REPO/$(dirname "$file")"
  cp "$file" "$REPO/$file"
done

cd "$REPO"
python3 -m py_compile \
  backend/services/cmdb_object_service.py \
  backend/services/relationship_service.py \
  backend/modules/platform.py \
  backend/api/server.py

if command -v node >/dev/null 2>&1; then
  node --check frontend/js/assets.js
  node --check frontend/js/cmdb-object.js
fi

sudo systemctl restart nexus-api.service
sleep 2
systemctl is-active --quiet nexus-api.service

echo "Backup: $BACKUP_DIR"
echo "Install PASS"
