#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/home/imdmanuc/Projects/Seymour/nexus-command-center}"

python3 "$ROOT/tests/test_sbp0271_jsonb_contract.py"
python3 "$ROOT/tests/test_sbp0271_acceptance_contract.py"

python3 -m py_compile \
  "$ROOT/backend/db/repositories/seymour_runtime_state_repository.py" \
  "$ROOT/scripts/acceptance/verify_sbp028_live_runtime_state.py"

echo "SBP-027.1 repository JSONB merge verification: PASS"
echo "SBP-027.1 acceptance compatibility verification: PASS"
echo "SBP-027.1 final verification: PASS"
