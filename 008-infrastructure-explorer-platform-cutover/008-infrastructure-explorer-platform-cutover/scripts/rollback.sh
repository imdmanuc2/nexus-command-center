#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE="$PACKAGE_ROOT/.last_backup_dir"
test -f "$STATE" || { echo "No backup state found."; exit 1; }
BACKUP_DIR="$(cat "$STATE")"
cd "$PROJECT_ROOT"
cp "$BACKUP_DIR/graph.html" frontend/graph.html
if [[ -f "$BACKUP_DIR/nexus-platform-explorer.js" ]]; then
  cp "$BACKUP_DIR/nexus-platform-explorer.js" frontend/js/nexus-platform-explorer.js
else
  rm -f frontend/js/nexus-platform-explorer.js
fi
echo "Package 008 rollback complete."
