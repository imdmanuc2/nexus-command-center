#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$PACKAGE_ROOT/../../.." && pwd)"

cd "$REPO_ROOT"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$REPO_ROOT/backups/package-065-$STAMP"
mkdir -p "$BACKUP/frontend/js" "$BACKUP/frontend/css" "$BACKUP/backend/services"
cp frontend/cmdb-object.html "$BACKUP/frontend/"
cp frontend/js/cmdb-object.js "$BACKUP/frontend/js/"
cp frontend/css/cmdb-object.css frontend/css/style.css "$BACKUP/frontend/css/"
cp backend/services/cmdb_object_service.py "$BACKUP/backend/services/"
cp -a "$PACKAGE_ROOT/payload/." "$REPO_ROOT/"
sudo systemctl restart nexus-api.service
for _ in $(seq 1 20); do
  if curl -fsS http://localhost:8080/cmdb-object.html >/dev/null; then break; fi
  sleep 1
done
echo "Backup: $BACKUP"
echo "Install PASS"
