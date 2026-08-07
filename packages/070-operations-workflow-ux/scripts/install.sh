#!/usr/bin/env bash
set -euo pipefail
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$PACKAGE_ROOT/../.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$REPO_ROOT/backups/package-070-$STAMP"
mkdir -p "$BACKUP/frontend/js" "$BACKUP/frontend/css" "$BACKUP/frontend"
for rel in frontend/js/nav.js frontend/css/style.css frontend/home-v2.html frontend/assets.html frontend/graph.html frontend/cmdb-object.html frontend/index.html; do
  if [ -f "$REPO_ROOT/$rel" ]; then
    mkdir -p "$BACKUP/$(dirname "$rel")"
    cp -a "$REPO_ROOT/$rel" "$BACKUP/$rel"
  fi
done
cp -a "$PACKAGE_ROOT/payload/frontend/js/nav.js" "$REPO_ROOT/frontend/js/nav.js"
cp -a "$PACKAGE_ROOT/payload/frontend/css/style.css" "$REPO_ROOT/frontend/css/style.css"
cp -a "$PACKAGE_ROOT/payload/frontend/home-v2.html" "$REPO_ROOT/frontend/home-v2.html"
cp -a "$PACKAGE_ROOT/payload/frontend/assets.html" "$REPO_ROOT/frontend/assets.html"
cp -a "$PACKAGE_ROOT/payload/frontend/graph.html" "$REPO_ROOT/frontend/graph.html"
cp -a "$PACKAGE_ROOT/payload/frontend/cmdb-object.html" "$REPO_ROOT/frontend/cmdb-object.html"
cp -a "$PACKAGE_ROOT/payload/frontend/index.html" "$REPO_ROOT/frontend/index.html"
if command -v systemctl >/dev/null 2>&1; then
  sudo systemctl restart nexus-api.service || true
fi
echo "Backup: $BACKUP"
echo "Install PASS"
