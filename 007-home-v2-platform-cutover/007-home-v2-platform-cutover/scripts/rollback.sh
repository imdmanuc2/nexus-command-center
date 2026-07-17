#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE="$PACKAGE_ROOT/.last_backup_dir"
test -f "$STATE" || { echo "No backup state found."; exit 1; }
BACKUP_DIR="$(cat "$STATE")"
cd "$PROJECT_ROOT"
cp "$BACKUP_DIR/home-v2.html" frontend/home-v2.html
if [[ -f "$BACKUP_DIR/nexus-platform-home.js" ]]; then
  cp "$BACKUP_DIR/nexus-platform-home.js" frontend/js/nexus-platform-home.js
else
  rm -f frontend/js/nexus-platform-home.js
fi
echo "Package 007 rollback complete."
