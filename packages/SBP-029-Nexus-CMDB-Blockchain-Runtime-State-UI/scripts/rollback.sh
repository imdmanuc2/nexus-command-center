#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/home/imdmanuc/Projects/Seymour/nexus-command-center}"
BACKUP="${2:-}"

[[ -f "$BACKUP/frontend/assets.html" ]] || {
  echo "Invalid SBP-029 backup: $BACKUP" >&2
  exit 1
}

cp \
  "$BACKUP/frontend/assets.html" \
  "$ROOT/frontend/assets.html"

cp \
  "$BACKUP/frontend/cmdb-object.html" \
  "$ROOT/frontend/cmdb-object.html"

rm -f \
  "$ROOT/frontend/js/cmdb-runtime-state.js" \
  "$ROOT/frontend/css/cmdb-runtime-state.css" \
  "$ROOT/tests/test_sbp029_contract.py"

echo "SBP-029 rollback: PASS"
