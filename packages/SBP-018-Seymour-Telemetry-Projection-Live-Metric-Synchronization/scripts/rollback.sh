#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-$HOME/Projects/Seymour/nexus-command-center}"
BACKUP="${2:-}"

[[ -f "$BACKUP/backend/api/server.py" ]] || { echo "Invalid SBP-018 backup: $BACKUP" >&2; exit 1; }

cp "$BACKUP/backend/api/server.py" "$ROOT/backend/api/server.py"
cp "$BACKUP/backend/db/repositories/seymour_registration_repository.py"    "$ROOT/backend/db/repositories/seymour_registration_repository.py"

rm -f   "$ROOT/backend/api/seymour_telemetry_routes.py"   "$ROOT/backend/services/seymour_telemetry_service.py"   "$ROOT/backend/db/repositories/seymour_telemetry_repository.py"   "$ROOT/tests/test_seymour_telemetry_projection.py"   "$ROOT/tests/test_seymour_telemetry_contract.py"

echo "SBP-018 source rollback: PASS"
echo "Existing current_metrics rows are intentionally retained."
