#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$PROJECT_ROOT/backend/data/private/package-backups/009-smart-topology-presentation-$STAMP"
cd "$PROJECT_ROOT"
mkdir -p "$BACKUP_DIR"
printf '%s\n' "$BACKUP_DIR" > "$PACKAGE_ROOT/.last_backup_dir"
cp frontend/js/graph.js "$BACKUP_DIR/graph.js"
python3 "$PACKAGE_ROOT/scripts/patch_graph.py"
node --check frontend/js/graph.js
echo "Package 009 installed."
echo "Backup: $BACKUP_DIR"
