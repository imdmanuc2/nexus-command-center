#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/home/imdmanuc/Projects/Seymour/nexus-command-center}"
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="$ROOT/backups/sbp-029-$STAMP"

"$PKG/scripts/doctor.sh" "$ROOT"

mkdir -p \
  "$BACKUP/frontend"

cp \
  "$ROOT/frontend/assets.html" \
  "$BACKUP/frontend/assets.html"

cp \
  "$ROOT/frontend/cmdb-object.html" \
  "$BACKUP/frontend/cmdb-object.html"

cd "$ROOT"

cp \
  "$PKG/payload/frontend/js/cmdb-runtime-state.js" \
  frontend/js/cmdb-runtime-state.js

cp \
  "$PKG/payload/frontend/css/cmdb-runtime-state.css" \
  frontend/css/cmdb-runtime-state.css

python3 \
  "$PKG/payload/patch_cmdb_pages.py"

mkdir -p tests

cp \
  "$PKG/payload/tests/test_sbp029_contract.py" \
  tests/test_sbp029_contract.py

echo "Backup: $BACKUP"
echo "SBP-029 install: PASS"
echo "No backend service restart is required for static frontend assets."
