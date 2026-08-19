#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"
cd "$REPO_ROOT"

STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$REPO_ROOT/backups/package-073-$STAMP"
mkdir -p "$BACKUP/frontend/js" "$BACKUP/frontend/css" "$BACKUP/docs"

cp frontend/home-v2.html "$BACKUP/frontend/home-v2.html"
cp frontend/js/home-v2.js "$BACKUP/frontend/js/home-v2.js"
cp frontend/css/home-v2.css "$BACKUP/frontend/css/home-v2.css"
if [[ -f docs/PRODUCT_PRINCIPLES.md ]]; then
  cp docs/PRODUCT_PRINCIPLES.md "$BACKUP/docs/PRODUCT_PRINCIPLES.md"
fi
printf '%s\n' "$BACKUP" > "$BACKUP_MARKER"

echo "Backup: $BACKUP"

mkdir -p frontend/js frontend/css docs
cp "$PAYLOAD_ROOT/frontend/home-v2.html" frontend/home-v2.html
cp "$PAYLOAD_ROOT/frontend/js/home-v2.js" frontend/js/home-v2.js
cp "$PAYLOAD_ROOT/frontend/css/home-v2.css" frontend/css/home-v2.css
cp "$PAYLOAD_ROOT/docs/PRODUCT_PRINCIPLES.md" docs/PRODUCT_PRINCIPLES.md

# Static frontend assets are served directly by nexus-api; no service restart is
# required and avoiding one prevents needless API downtime during UX installs.
echo "Install PASS"
