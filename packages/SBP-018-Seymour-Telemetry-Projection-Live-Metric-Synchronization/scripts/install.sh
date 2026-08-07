#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-$HOME/Projects/Seymour/nexus-command-center}"
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="$ROOT/backups/sbp-018-$STAMP"

"$PKG/scripts/doctor.sh" "$ROOT"

mkdir -p "$BACKUP/backend/api" "$BACKUP/backend/db/repositories"
cp "$ROOT/backend/api/server.py" "$BACKUP/backend/api/server.py"
cp "$ROOT/backend/db/repositories/seymour_registration_repository.py"    "$BACKUP/backend/db/repositories/seymour_registration_repository.py"

mkdir -p "$ROOT/backend/db/repositories" "$ROOT/backend/services" "$ROOT/backend/api" "$ROOT/tests"

cp "$PKG/payload/backend/db/repositories/seymour_telemetry_repository.py"    "$ROOT/backend/db/repositories/seymour_telemetry_repository.py"
cp "$PKG/payload/backend/services/seymour_telemetry_service.py"    "$ROOT/backend/services/seymour_telemetry_service.py"
cp "$PKG/payload/backend/api/seymour_telemetry_routes.py"    "$ROOT/backend/api/seymour_telemetry_routes.py"
cp "$PKG/payload/tests/test_seymour_telemetry_projection.py"    "$ROOT/tests/test_seymour_telemetry_projection.py"
cp "$PKG/payload/tests/test_seymour_telemetry_contract.py"    "$ROOT/tests/test_seymour_telemetry_contract.py"

cd "$ROOT"
python3 "$PKG/payload/patch_registration_repository.py"
python3 "$PKG/payload/patch_server.py"

echo "Backup: $BACKUP"
echo "SBP-018 install: PASS"
echo "nexus-api.service was not restarted."
