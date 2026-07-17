#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$PROJECT_ROOT/backend/data/private/package-backups/008-infrastructure-explorer-platform-cutover-$STAMP"
cd "$PROJECT_ROOT"
mkdir -p "$BACKUP_DIR" frontend/js
printf '%s\n' "$BACKUP_DIR" > "$PACKAGE_ROOT/.last_backup_dir"
cp frontend/graph.html "$BACKUP_DIR/graph.html"
[[ -f frontend/js/nexus-platform-explorer.js ]] && cp frontend/js/nexus-platform-explorer.js "$BACKUP_DIR/"
install -m 0644 "$PACKAGE_ROOT/frontend/js/nexus-platform-explorer.js" frontend/js/nexus-platform-explorer.js
python3 "$PACKAGE_ROOT/scripts/patch_graph.py"
grep -q 'nexus-platform-explorer.js' frontend/graph.html
echo "Package 008 installed."
echo "Backup: $BACKUP_DIR"
