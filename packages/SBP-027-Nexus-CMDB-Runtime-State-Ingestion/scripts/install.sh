#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/home/imdmanuc/Projects/Seymour/nexus-command-center}"
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="$ROOT/backups/sbp-027-$STAMP"

"$PKG/scripts/doctor.sh" "$ROOT"

mkdir -p \
  "$BACKUP/backend/db/repositories"

cp \
  "$ROOT/backend/db/repositories/seymour_registration_repository.py" \
  "$BACKUP/backend/db/repositories/seymour_registration_repository.py"

if [[ -f \
  "$ROOT/backend/db/repositories/seymour_runtime_state_repository.py" ]]; then
  cp \
    "$ROOT/backend/db/repositories/seymour_runtime_state_repository.py" \
    "$BACKUP/backend/db/repositories/seymour_runtime_state_repository.py"
fi

cd "$ROOT"

cp \
  "$PKG/payload/backend/db/repositories/seymour_runtime_state_repository.py" \
  backend/db/repositories/seymour_runtime_state_repository.py

python3 \
  "$PKG/payload/patch_registration_repository.py"

mkdir -p tests

cp \
  "$PKG/payload/tests/test_sbp027_contract.py" \
  tests/test_sbp027_contract.py

cp \
  "$PKG/payload/tests/test_sbp027_mapping.py" \
  tests/test_sbp027_mapping.py

echo "Backup: $BACKUP"
echo "SBP-027 install: PASS"
echo "nexus-api.service was not restarted."
