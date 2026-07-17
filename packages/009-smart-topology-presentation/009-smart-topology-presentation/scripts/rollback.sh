#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STATE="$PACKAGE_ROOT/.last_backup_dir"
test -f "$STATE" || { echo "No backup state found."; exit 1; }
BACKUP_DIR="$(cat "$STATE")"
cd "$PROJECT_ROOT"
cp "$BACKUP_DIR/graph.js" frontend/js/graph.js
node --check frontend/js/graph.js
echo "Package 009 rollback complete."
