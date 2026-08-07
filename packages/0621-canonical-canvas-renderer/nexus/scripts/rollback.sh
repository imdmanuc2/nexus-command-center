#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
BACKUP="${1:-}"

if [[ -z "$BACKUP" ]]; then
  BACKUP="$(find "$ROOT/backups" -maxdepth 1 -type d -name 'package-0621-*' | sort | tail -n 1)"
fi

if [[ -z "$BACKUP" || ! -f "$BACKUP/frontend/js/graph.js" ]]; then
  echo "FAIL: valid Package 062.1 backup not found" >&2
  exit 1
fi

cp -a "$BACKUP/frontend/js/graph.js" "$ROOT/frontend/js/graph.js"
sudo systemctl restart nexus-api.service
echo "Rollback PASS: $BACKUP"
