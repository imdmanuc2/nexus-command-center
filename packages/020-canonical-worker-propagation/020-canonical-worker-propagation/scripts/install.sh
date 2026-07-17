#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$ROOT/backend/data/private/package-backups/020-canonical-worker-propagation-$STAMP"

cd "$ROOT"

mkdir -p "$BACKUP"
printf '%s\n' "$BACKUP" > "$PKG/.last_backup_dir"

cp \
  scripts/sync_platform_inventory.py \
  "$BACKUP/sync_platform_inventory.py"

python3 "$PKG/scripts/patch_inventory_sync.py"

python3 -m py_compile \
  scripts/sync_platform_inventory.py

echo "Package 020 installed."
echo "Backup: $BACKUP"
