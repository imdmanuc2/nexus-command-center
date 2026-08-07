#!/usr/bin/env bash
set -euo pipefail
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$PACKAGE_ROOT/../../.." && pwd)"
BACKUP_ROOT="$REPO_ROOT/backups/package-068-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_ROOT/frontend/js" "$BACKUP_ROOT/frontend/css"
cd "$REPO_ROOT"
cp frontend/assets.html "$BACKUP_ROOT/frontend/assets.html"
cp frontend/js/assets.js "$BACKUP_ROOT/frontend/js/assets.js"
cp frontend/css/style.css "$BACKUP_ROOT/frontend/css/style.css"
install -m 0644 "$PACKAGE_ROOT/payload/frontend/assets.html" frontend/assets.html
install -m 0644 "$PACKAGE_ROOT/payload/frontend/js/assets.js" frontend/js/assets.js
install -m 0644 "$PACKAGE_ROOT/payload/frontend/css/style.css" frontend/css/style.css
if command -v sudo >/dev/null 2>&1 && systemctl list-unit-files nexus-api.service >/dev/null 2>&1; then
  sudo systemctl restart nexus-api.service || true
fi
echo "Backup: $BACKUP_ROOT"
echo "Install PASS"
