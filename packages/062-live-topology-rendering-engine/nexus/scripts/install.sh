#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$ROOT/backups/package-062-$STAMP"

mkdir -p "$BACKUP/frontend/js"
cp -a "$ROOT/frontend/js/graph.js" "$BACKUP/frontend/js/graph.js"
mkdir -p "$ROOT/frontend/js"
cp -a "$PKG_ROOT/payload/frontend/js/graph.js" "$ROOT/frontend/js/graph.js"

node --check "$ROOT/frontend/js/graph.js"

if sudo systemctl list-unit-files nexus-api.service >/dev/null 2>&1; then
  sudo systemctl restart nexus-api.service
  for _ in {1..20}; do
    if curl -fsS http://127.0.0.1:8080/graph.html >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
fi

echo "Backup: $BACKUP"
echo "Install PASS"
