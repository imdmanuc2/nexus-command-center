#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"
cd "$PROJECT_ROOT"

cp backend/core/asset_manager.py "backend/core/asset_manager.py.before-postgresql-writes-$STAMP"
install -m 0644 "$PACKAGE_ROOT/backend/db/repositories/asset_repository_extensions.py" \
  backend/db/repositories/asset_repository_extensions.py
python3 "$PACKAGE_ROOT/scripts/patch_asset_manager.py"

python3 -m py_compile \
  backend/core/asset_manager.py \
  backend/core/assets.py \
  backend/core/reconciliation_engine.py \
  backend/db/repositories/asset_repository.py \
  backend/db/repositories/asset_repository_extensions.py \
  backend/api/server.py

echo
printf 'Package 004 installed. Restart Nexus, then run scripts/verify.sh.\n'
