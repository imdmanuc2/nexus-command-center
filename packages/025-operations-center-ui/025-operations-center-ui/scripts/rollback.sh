#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

test -f "$PKG/.last_backup_dir" || {
  echo "No Package 025 backup state found."
  exit 1
}

BACKUP="$(cat "$PKG/.last_backup_dir")"

cd "$ROOT"

cp \
  "$BACKUP/frontend/js/nav.js" \
  frontend/js/nav.js

if [ -f "$BACKUP/backend/api/server.py" ]; then
  cp \
    "$BACKUP/backend/api/server.py" \
    backend/api/server.py
fi

rm -f \
  frontend/operations-center.html \
  frontend/css/operations-center.css \
  frontend/js/operations-center.js

sudo systemctl restart nexus-api.service

echo "Package 025 rollback complete."
