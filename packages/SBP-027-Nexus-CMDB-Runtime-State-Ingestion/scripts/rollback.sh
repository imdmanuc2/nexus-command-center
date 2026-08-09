#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/home/imdmanuc/Projects/Seymour/nexus-command-center}"
BACKUP="${2:-}"

[[ -f \
  "$BACKUP/backend/db/repositories/seymour_registration_repository.py" ]] || {
  echo "Invalid SBP-027 backup: $BACKUP" >&2
  exit 1
}

cp \
  "$BACKUP/backend/db/repositories/seymour_registration_repository.py" \
  "$ROOT/backend/db/repositories/seymour_registration_repository.py"

if [[ -f \
  "$BACKUP/backend/db/repositories/seymour_runtime_state_repository.py" ]]; then
  cp \
    "$BACKUP/backend/db/repositories/seymour_runtime_state_repository.py" \
    "$ROOT/backend/db/repositories/seymour_runtime_state_repository.py"
else
  rm -f \
    "$ROOT/backend/db/repositories/seymour_runtime_state_repository.py"
fi

rm -f \
  "$ROOT/tests/test_sbp027_contract.py" \
  "$ROOT/tests/test_sbp027_mapping.py"

echo "SBP-027 rollback: PASS"
