#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

test -f "$PKG/.last_backup_dir" || {
  echo "No Package 020 backup state found."
  exit 1
}

BACKUP="$(cat "$PKG/.last_backup_dir")"
cd "$ROOT"

cp \
  "$BACKUP/sync_platform_inventory.py" \
  scripts/sync_platform_inventory.py

echo "Package 020 rollback complete."
