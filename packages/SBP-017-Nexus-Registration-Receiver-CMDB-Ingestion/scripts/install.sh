#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-$HOME/Projects/Seymour/nexus-command-center}"
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP="$ROOT/backups/sbp-017-$STAMP"

"$PKG/scripts/doctor.sh" "$ROOT"

mkdir -p "$BACKUP/backend/api"
cp "$ROOT/backend/api/server.py" "$BACKUP/backend/api/server.py"

mkdir -p \
  "$ROOT/backend/db/repositories" \
  "$ROOT/backend/services" \
  "$ROOT/backend/api" \
  "$ROOT/backend/db/migrations" \
  "$ROOT/tests"

cp "$PKG/payload/backend/db/repositories/seymour_registration_repository.py" \
  "$ROOT/backend/db/repositories/seymour_registration_repository.py"

cp "$PKG/payload/backend/services/seymour_registration_service.py" \
  "$ROOT/backend/services/seymour_registration_service.py"

cp "$PKG/payload/backend/api/seymour_registration_routes.py" \
  "$ROOT/backend/api/seymour_registration_routes.py"

cp "$PKG/payload/backend/db/migrations/038_seymour_registration_receiver.sql" \
  "$ROOT/backend/db/migrations/038_seymour_registration_receiver.sql"

cp "$PKG/payload/tests/test_seymour_registration_contract.py" \
  "$ROOT/tests/test_seymour_registration_contract.py"

cp "$PKG/payload/tests/test_seymour_registration_projection.py" \
  "$ROOT/tests/test_seymour_registration_projection.py"

cd "$ROOT"
python3 "$PKG/payload/patch_server.py"

set -a
source backend/data/private/cmdb.env
set +a
export PGPASSWORD="$NEXUS_DB_PASSWORD"

psql \
  -h "$NEXUS_DB_HOST" \
  -p "$NEXUS_DB_PORT" \
  -U "$NEXUS_DB_USER" \
  -d "$NEXUS_DB_NAME" \
  -v ON_ERROR_STOP=1 \
  -f backend/db/migrations/038_seymour_registration_receiver.sql

TOKEN_FILE="$ROOT/backend/data/private/seymour-registration.env"

if [[ ! -s "$TOKEN_FILE" ]]; then
  TOKEN="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
)"
  printf 'NEXUS_SEYMOUR_REGISTRATION_TOKEN=%s\n' "$TOKEN" > "$TOKEN_FILE"
  chmod 600 "$TOKEN_FILE"
fi

if command -v sudo >/dev/null 2>&1; then
  sudo mkdir -p /etc/systemd/system/nexus-api.service.d
  printf '%s\n' \
    "[Service]" \
    "EnvironmentFile=$TOKEN_FILE" \
    | sudo tee /etc/systemd/system/nexus-api.service.d/seymour-registration.conf >/dev/null
  sudo systemctl daemon-reload
fi

echo "Backup: $BACKUP"
echo "Receiver token: $TOKEN_FILE"
echo "SBP-017 install: PASS"
echo "nexus-api.service was not restarted."
