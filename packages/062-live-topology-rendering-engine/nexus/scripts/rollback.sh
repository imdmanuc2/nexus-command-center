#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
BACKUP="${1:-}"

if [[ -z "$BACKUP" ]]; then
  BACKUP="$(find "$ROOT/backups" -maxdepth 1 -type d -name 'package-062-*' | sort | tail -n 1)"
fi

if [[ -z "$BACKUP" || ! -f "$BACKUP/frontend/js/graph.js" ]]; then
  echo "FAIL: valid Package 062 backup not found" >&2
  exit 1
fi

cp -a "$BACKUP/frontend/js/graph.js" "$ROOT/frontend/js/graph.js"
node --check "$ROOT/frontend/js/graph.js"

if sudo systemctl list-unit-files nexus-api.service >/dev/null 2>&1; then
  sudo systemctl restart nexus-api.service
fi

echo "Rollback PASS: $BACKUP"
