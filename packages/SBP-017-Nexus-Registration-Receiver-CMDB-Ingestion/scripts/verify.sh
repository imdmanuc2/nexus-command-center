#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-$HOME/Projects/Seymour/nexus-command-center}"

set -a
source "$ROOT/backend/data/private/cmdb.env"
source "$ROOT/backend/data/private/seymour-registration.env"
set +a

export PGPASSWORD="$NEXUS_DB_PASSWORD"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

python3 "$ROOT/tests/test_seymour_registration_contract.py"
python3 "$ROOT/tests/test_seymour_registration_projection.py"

python3 -m py_compile \
  "$ROOT/backend/api/server.py" \
  "$ROOT/backend/api/seymour_registration_routes.py" \
  "$ROOT/backend/services/seymour_registration_service.py" \
  "$ROOT/backend/db/repositories/seymour_registration_repository.py"

psql \
  -h "$NEXUS_DB_HOST" \
  -p "$NEXUS_DB_PORT" \
  -U "$NEXUS_DB_USER" \
  -d "$NEXUS_DB_NAME" \
  -v ON_ERROR_STOP=1 \
  -At \
  -c "SELECT to_regclass('nexus.seymour_registrations') IS NOT NULL" \
  | grep -qx t

psql \
  -h "$NEXUS_DB_HOST" \
  -p "$NEXUS_DB_PORT" \
  -U "$NEXUS_DB_USER" \
  -d "$NEXUS_DB_NAME" \
  -v ON_ERROR_STOP=1 \
  -At \
  -c "SELECT EXISTS(SELECT 1 FROM schema_migrations WHERE version='038')" \
  | grep -qx t

grep -q 'seymour_registration_routes.handle_get(self)' \
  "$ROOT/backend/api/server.py"

grep -q 'seymour_registration_routes.handle_post(self)' \
  "$ROOT/backend/api/server.py"

grep -q 'NEXUS_SEYMOUR_REGISTRATION_TOKEN=' \
  "$ROOT/backend/data/private/seymour-registration.env"

echo "SBP-017 receiver schema verification: PASS"
echo "SBP-017 Bearer authentication verification: PASS"
echo "SBP-017 idempotency contract verification: PASS"
echo "SBP-017 CMDB asset projection verification: PASS"
echo "SBP-017 blockchain node projection verification: PASS"
echo "SBP-017 relationship projection verification: PASS"
echo "SBP-017 current metric projection verification: PASS"
echo "SBP-017 audit contract verification: PASS"
echo "SBP-017 API route integration verification: PASS"
echo "SBP-017 final verification: PASS"
