#!/usr/bin/env bash
set -euo pipefail
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$PACKAGE_ROOT/../../.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$REPO_ROOT/backups/package-067-$STAMP"
mkdir -p "$BACKUP/frontend/js" "$BACKUP/frontend/css" "$BACKUP/backend/services"
for f in frontend/cmdb-object.html frontend/js/cmdb-object.js frontend/css/cmdb-object.css backend/services/cmdb_object_service.py; do
  [[ -f "$REPO_ROOT/$f" ]] && cp "$REPO_ROOT/$f" "$BACKUP/$f"
done
cp "$PACKAGE_ROOT/payload/frontend/cmdb-object.html" "$REPO_ROOT/frontend/cmdb-object.html"
cp "$PACKAGE_ROOT/payload/frontend/js/cmdb-object.js" "$REPO_ROOT/frontend/js/cmdb-object.js"
cp "$PACKAGE_ROOT/payload/frontend/css/cmdb-object.css" "$REPO_ROOT/frontend/css/cmdb-object.css"
cp "$PACKAGE_ROOT/payload/backend/services/cmdb_object_service.py" "$REPO_ROOT/backend/services/cmdb_object_service.py"
if command -v systemctl >/dev/null 2>&1; then sudo systemctl restart nexus-api.service || true; fi
echo "Backup: $BACKUP"
echo "Install PASS"
