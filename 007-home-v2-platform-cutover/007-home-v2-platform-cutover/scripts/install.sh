#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$PROJECT_ROOT/backend/data/private/package-backups/007-home-v2-platform-cutover-$STAMP"
cd "$PROJECT_ROOT"
mkdir -p "$BACKUP_DIR" frontend/js
printf '%s\n' "$BACKUP_DIR" > "$PACKAGE_ROOT/.last_backup_dir"
cp frontend/home-v2.html "$BACKUP_DIR/home-v2.html"
[[ -f frontend/js/nexus-platform-home.js ]] && cp frontend/js/nexus-platform-home.js "$BACKUP_DIR/"
install -m 0644 "$PACKAGE_ROOT/frontend/js/nexus-platform-home.js" frontend/js/nexus-platform-home.js
python3 "$PACKAGE_ROOT/scripts/patch_home.py"
grep -q 'nexus-platform-home.js' frontend/home-v2.html
echo "Package 007 installed."
echo "Backup: $BACKUP_DIR"
