#!/usr/bin/env bash
set -euo pipefail
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$PACKAGE_ROOT/../../.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$REPO_ROOT/backups/package-069-$STAMP"
mkdir -p "$BACKUP/frontend/js" "$BACKUP/frontend/css"
cp "$REPO_ROOT/frontend/cmdb-object.html" "$BACKUP/frontend/cmdb-object.html"
cp "$REPO_ROOT/frontend/js/cmdb-object.js" "$BACKUP/frontend/js/cmdb-object.js"
cp "$REPO_ROOT/frontend/css/cmdb-object.css" "$BACKUP/frontend/css/cmdb-object.css"
cp "$PACKAGE_ROOT/payload/frontend/cmdb-object.html" "$REPO_ROOT/frontend/cmdb-object.html"
cp "$PACKAGE_ROOT/payload/frontend/js/cmdb-object.js" "$REPO_ROOT/frontend/js/cmdb-object.js"
cp "$PACKAGE_ROOT/payload/frontend/css/cmdb-object.css" "$REPO_ROOT/frontend/css/cmdb-object.css"
echo "Backup: $BACKUP"
if command -v sudo >/dev/null 2>&1; then
  sudo systemctl restart nexus-api.service || true
fi
echo "Install PASS"
