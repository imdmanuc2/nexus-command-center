#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/home/imdmanuc/Projects/Seymour/nexus-command-center}"

python3 \
  "$ROOT/tests/test_sbp029_contract.py"

grep -q \
  '/js/cmdb-runtime-state.js' \
  "$ROOT/frontend/cmdb-object.html"

grep -q \
  '/js/cmdb-runtime-state.js' \
  "$ROOT/frontend/assets.html"

echo "SBP-029 CMDB object runtime-state verification: PASS"
echo "SBP-029 CMDB asset-list runtime-state verification: PASS"
echo "SBP-029 final verification: PASS"
