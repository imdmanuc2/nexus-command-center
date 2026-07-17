#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date +%Y%m%d-%H%M%S)"

log(){ printf '\n==> %s\n' "$*"; }
die(){ printf '\nERROR: %s\n' "$*" >&2; exit 1; }

[[ -f "$PROJECT_ROOT/backend/db/connection.py" ]] \
  || die "Missing $PROJECT_ROOT/backend/db/connection.py"

mkdir -p \
  "$PROJECT_ROOT/backend/db/importers" \
  "$PROJECT_ROOT/backend/db/repositories" \
  "$PROJECT_ROOT/backend/services"

touch \
  "$PROJECT_ROOT/backend/db/__init__.py" \
  "$PROJECT_ROOT/backend/db/importers/__init__.py" \
  "$PROJECT_ROOT/backend/db/repositories/__init__.py" \
  "$PROJECT_ROOT/backend/services/__init__.py"

if [[ -f "$PROJECT_ROOT/backend/modules/cmdb.py" ]]; then
  cp "$PROJECT_ROOT/backend/modules/cmdb.py" \
     "$PROJECT_ROOT/backend/modules/cmdb.py.before-postgresql-assets-$STAMP"
fi

log "Installing Milestone 1 files"
install -m 0644 "$PACKAGE_ROOT/backend/db/repositories/asset_repository.py" \
  "$PROJECT_ROOT/backend/db/repositories/asset_repository.py"
install -m 0644 "$PACKAGE_ROOT/backend/db/importers/import_assets_json.py" \
  "$PROJECT_ROOT/backend/db/importers/import_assets_json.py"
install -m 0644 "$PACKAGE_ROOT/backend/services/cmdb_service.py" \
  "$PROJECT_ROOT/backend/services/cmdb_service.py"
install -m 0644 "$PACKAGE_ROOT/backend/modules/cmdb.py" \
  "$PROJECT_ROOT/backend/modules/cmdb.py"

cd "$PROJECT_ROOT"
log "Compiling"
python3 -m py_compile \
  backend/db/connection.py \
  backend/db/repositories/asset_repository.py \
  backend/db/importers/import_assets_json.py \
  backend/services/cmdb_service.py \
  backend/modules/cmdb.py

log "Dry-run import"
python3 -m backend.db.importers.import_assets_json --dry-run

echo
echo "Milestone 1 installed."
echo "Next: python3 -m backend.db.importers.import_assets_json"
