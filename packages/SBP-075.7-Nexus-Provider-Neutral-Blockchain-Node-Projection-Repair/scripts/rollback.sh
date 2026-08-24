#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PKG="$ROOT/packages/SBP-075.7-Nexus-Provider-Neutral-Blockchain-Node-Projection-Repair"
BACKUP="$PKG/backups"

cd "$ROOT"

echo "===== SBP-075.7 ROLLBACK ====="

test -f "$BACKUP/seymour_registration_repository.py.before-075.7"
test -f "$BACKUP/seymour_telemetry_repository.py.before-075.7"

cp -a \
  "$BACKUP/seymour_registration_repository.py.before-075.7" \
  backend/db/repositories/seymour_registration_repository.py

cp -a \
  "$BACKUP/seymour_telemetry_repository.py.before-075.7" \
  backend/db/repositories/seymour_telemetry_repository.py

rm -f tests/test_sbp075_7_provider_neutral_projection.py

python3 -m py_compile \
  backend/db/repositories/seymour_registration_repository.py \
  backend/db/repositories/seymour_telemetry_repository.py

echo "SBP-075.7 rollback: PASS"
