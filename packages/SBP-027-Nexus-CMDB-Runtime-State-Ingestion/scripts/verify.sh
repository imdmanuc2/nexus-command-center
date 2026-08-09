#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/home/imdmanuc/Projects/Seymour/nexus-command-center}"

python3 "$ROOT/tests/test_sbp027_contract.py"
python3 "$ROOT/tests/test_sbp027_mapping.py"

python3 -m py_compile \
  "$ROOT/backend/db/repositories/seymour_registration_repository.py" \
  "$ROOT/backend/db/repositories/seymour_runtime_state_repository.py"

echo "SBP-027 repository integration verification: PASS"
echo "SBP-027 runtime-state CMDB contract verification: PASS"
echo "SBP-027 final verification: PASS"
