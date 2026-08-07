#!/usr/bin/env bash
set -euo pipefail
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$PACKAGE_ROOT/../../.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$REPO_ROOT/backups/package-066-$STAMP"
mkdir -p "$BACKUP/frontend/js"
for f in frontend/assets.html frontend/cmdb-object.html; do cp "$REPO_ROOT/$f" "$BACKUP/$f"; done
for f in frontend/js/assets.js frontend/js/nav.js frontend/js/cmdb-object.js frontend/js/graph.js; do cp "$REPO_ROOT/$f" "$BACKUP/$f"; done
cp -a "$PACKAGE_ROOT/payload/frontend/." "$REPO_ROOT/frontend/"
sudo systemctl restart nexus-api.service
sleep 2
echo "Backup: $BACKUP"
echo "Install PASS"
