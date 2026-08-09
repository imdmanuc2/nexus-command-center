#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/home/imdmanuc/Projects/Seymour/nexus-command-center}"

rm -f \
  "$ROOT/tests/test_sbp028_contract.py" \
  "$ROOT/scripts/acceptance/verify_sbp028_live_runtime_state.py"

echo "SBP-028 rollback: PASS"
