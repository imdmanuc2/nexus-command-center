#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
PKG="$ROOT/packages/SBP-075.7-Nexus-Provider-Neutral-Blockchain-Node-Projection-Repair"
BACKUP="$PKG/backups"

cd "$ROOT"

echo "===== SBP-075.7 INSTALL ====="

mkdir -p "$BACKUP"

cp -a \
  backend/db/repositories/seymour_registration_repository.py \
  "$BACKUP/seymour_registration_repository.py.before-075.7"

cp -a \
  backend/db/repositories/seymour_telemetry_repository.py \
  "$BACKUP/seymour_telemetry_repository.py.before-075.7"

python3 "$PKG/scripts/patch.py"

python3 -m py_compile \
  backend/db/repositories/seymour_registration_repository.py \
  backend/db/repositories/seymour_telemetry_repository.py

echo "SBP-075.7 install: PASS"
