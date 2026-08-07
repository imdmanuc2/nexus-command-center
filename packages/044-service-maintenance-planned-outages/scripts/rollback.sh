#!/usr/bin/env bash
set -euo pipefail
PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(cd "$PKG_DIR/../.." && pwd)"
BACKUP="${1:-$(find "$ROOT/packages/backups" -maxdepth 1 -type d -name '044-service-maintenance-planned-outages-*' | sort | tail -1)}"
test -n "$BACKUP"
test -d "$BACKUP"

for f in \
  backend/api/server.py \
  backend/db/repositories/maintenance_repository.py \
  frontend/service-operations.html \
  frontend/css/service-operations.css \
  frontend/js/service-operations.js
do
  test -f "$BACKUP/$f" && cp "$BACKUP/$f" "$ROOT/$f"
done

rm -f \
  "$ROOT/backend/db/repositories/service_maintenance_repository.py" \
  "$ROOT/backend/services/service_maintenance_service.py" \
  "$ROOT/backend/modules/platform_service_maintenance.py"

sudo systemctl restart nexus-api.service
echo "Package 044 application files rolled back from: $BACKUP"
echo "Migration 033 data was intentionally retained."
