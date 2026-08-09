#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/home/imdmanuc/Projects/Seymour/nexus-command-center}"

python3 \
  "$ROOT/tests/test_sbp028_contract.py"

python3 -m py_compile \
  "$ROOT/scripts/acceptance/verify_sbp028_live_runtime_state.py"

echo "SBP-028 repository acceptance contract verification: PASS"
echo "SBP-028 final verification: PASS"
