#!/usr/bin/env bash
set -euo pipefail
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(cd "$PKG/../.." && pwd)"
cd "$ROOT"

BACKUP="$ROOT/backend/data/private/package-backups/048-verification-framework-evidence-engine-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP"
for path in \
  backend/db/repositories/verification_repository.py \
  backend/services/verification_service.py \
  backend/jobs/verification_worker.py \
  backend/modules/platform_verifications.py \
  backend/api/patch_verification_routes.py \
  backend/api/server.py; do
  if [[ -f "$path" ]]; then
    mkdir -p "$BACKUP/$(dirname "$path")"
    cp -a "$path" "$BACKUP/$path"
  fi
done

for path in \
  backend/db/migrations/037_verification_framework_evidence_engine.sql \
  backend/db/repositories/verification_repository.py \
  backend/services/verification_service.py \
  backend/jobs/verification_worker.py \
  backend/modules/platform_verifications.py \
  backend/api/patch_verification_routes.py; do
  install -D -m 0644 "$PKG/$path" "$ROOT/$path"
done

set -a
source backend/data/private/cmdb.env
set +a
export PGPASSWORD="$NEXUS_DB_PASSWORD"
psql -v ON_ERROR_STOP=1 -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" \
  -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME" \
  -f backend/db/migrations/037_verification_framework_evidence_engine.sql

/usr/bin/python3 backend/api/patch_verification_routes.py
/usr/bin/python3 -m py_compile \
  backend/api/server.py \
  backend/api/patch_verification_routes.py \
  backend/modules/platform_verifications.py

SERVICE_TMP="$(mktemp)"
trap 'rm -f "$SERVICE_TMP"' EXIT
sed \
  -e "s|__NEXUS_USER__|$(id -un)|g" \
  -e "s|__NEXUS_ROOT__|$ROOT|g" \
  "$PKG/systemd/nexus-verification-worker.service" > "$SERVICE_TMP"

sudo install -m 0644 "$SERVICE_TMP" /etc/systemd/system/nexus-verification-worker.service
sudo systemctl daemon-reload
sudo systemctl enable nexus-verification-worker.service
sudo systemctl restart nexus-verification-worker.service
sudo systemctl restart nexus-api.service

echo "Package 048 install PASS"
