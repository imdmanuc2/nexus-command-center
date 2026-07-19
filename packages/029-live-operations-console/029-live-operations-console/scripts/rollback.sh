#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP="$(cat "$PKG/.last_backup_dir" 2>/dev/null || true)"
[[ -n "$BACKUP" && -d "$BACKUP" ]] || { echo 'No Package 029 backup found.' >&2; exit 1; }
cd "$ROOT"
cp -r "$BACKUP/"* "$ROOT/"
sudo systemctl restart nexus-api.service
echo "Package 029 application files rolled back from $BACKUP"
echo 'Migration 020 tables were retained to preserve immutable operation history.'
