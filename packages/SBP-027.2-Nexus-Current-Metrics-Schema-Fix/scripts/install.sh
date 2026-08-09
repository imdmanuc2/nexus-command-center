#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/home/imdmanuc/Projects/Seymour/nexus-command-center}"
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="$ROOT/backups/sbp-0272-$STAMP"
"$PKG/scripts/doctor.sh" "$ROOT"
mkdir -p "$BACKUP/backend/db/repositories" "$BACKUP/scripts/acceptance"
cp "$ROOT/backend/db/repositories/seymour_runtime_state_repository.py" "$BACKUP/backend/db/repositories/seymour_runtime_state_repository.py"
cp "$ROOT/scripts/acceptance/verify_sbp028_live_runtime_state.py" "$BACKUP/scripts/acceptance/verify_sbp028_live_runtime_state.py"
cd "$ROOT"
python3 "$PKG/payload/replace_runtime_state_repository.py"
python3 "$PKG/payload/patch_sbp028_acceptance.py"
mkdir -p tests
cp "$PKG/payload/tests/test_sbp0272_schema_contract.py" tests/test_sbp0272_schema_contract.py
cp "$PKG/payload/tests/test_sbp0272_acceptance_contract.py" tests/test_sbp0272_acceptance_contract.py
echo "Backup: $BACKUP"
echo "SBP-027.2 install: PASS"
echo "nexus-api.service was not restarted."
