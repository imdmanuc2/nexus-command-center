#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-$HOME/Projects/Seymour/nexus-command-center}"
BACKUP="${2:-}"

[[ -f "$BACKUP/backend/api/server.py" ]] || {
  echo "Invalid SBP-017 backup: $BACKUP" >&2
  exit 1
}

cp "$BACKUP/backend/api/server.py" "$ROOT/backend/api/server.py"

rm -f \
  "$ROOT/backend/api/seymour_registration_routes.py" \
  "$ROOT/backend/services/seymour_registration_service.py" \
  "$ROOT/backend/db/repositories/seymour_registration_repository.py" \
  "$ROOT/tests/test_seymour_registration_contract.py" \
  "$ROOT/tests/test_seymour_registration_projection.py"

echo "SBP-017 source rollback: PASS"
echo "Migration 038 and CMDB data are intentionally retained."
