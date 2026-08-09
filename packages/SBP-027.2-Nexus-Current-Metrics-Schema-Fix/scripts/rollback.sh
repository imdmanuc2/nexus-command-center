#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/home/imdmanuc/Projects/Seymour/nexus-command-center}"
BACKUP="${2:-}"
[[ -f "$BACKUP/backend/db/repositories/seymour_runtime_state_repository.py" ]] || { echo "Invalid SBP-027.2 backup: $BACKUP" >&2; exit 1; }
cp "$BACKUP/backend/db/repositories/seymour_runtime_state_repository.py" "$ROOT/backend/db/repositories/seymour_runtime_state_repository.py"
cp "$BACKUP/scripts/acceptance/verify_sbp028_live_runtime_state.py" "$ROOT/scripts/acceptance/verify_sbp028_live_runtime_state.py"
rm -f "$ROOT/tests/test_sbp0272_schema_contract.py" "$ROOT/tests/test_sbp0272_acceptance_contract.py"
echo "SBP-027.2 rollback: PASS"
