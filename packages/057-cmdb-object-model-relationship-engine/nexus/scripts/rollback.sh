#!/usr/bin/env bash
set -euo pipefail

REPO="${NEXUS_REPO:-$HOME/Projects/Seymour/nexus-command-center}"
MARKER="$REPO/.package-057-last-backup"
test -f "$MARKER" || { echo "FAIL: no Package 057 backup marker"; exit 1; }
BACKUP_DIR="$(cat "$MARKER")"
test -d "$BACKUP_DIR" || { echo "FAIL: backup directory missing: $BACKUP_DIR"; exit 1; }

cd "$BACKUP_DIR"
find backend frontend -type f -print0 | while IFS= read -r -d '' file; do
  mkdir -p "$REPO/$(dirname "$file")"
  cp "$file" "$REPO/$file"
done

rm -f \
  "$REPO/backend/services/cmdb_object_service.py" \
  "$REPO/frontend/cmdb-object.html" \
  "$REPO/frontend/js/cmdb-object.js" \
  "$REPO/frontend/css/cmdb-object.css"

sudo systemctl restart nexus-api.service
sleep 2
systemctl is-active --quiet nexus-api.service

echo "Rollback PASS"
