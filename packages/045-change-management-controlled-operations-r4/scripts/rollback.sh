#!/usr/bin/env bash
set -euo pipefail
PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(cd "$PKG_DIR/../.." && pwd)"
BACKUP="${1:-$(find "$ROOT/packages/backups" -maxdepth 1 -type d -name '045-change-management-controlled-operations-*' | sort | tail -1)}"
test -n "$BACKUP"; test -d "$BACKUP"
for f in backend/api/server.py frontend/service-operations.html frontend/css/service-operations.css frontend/js/service-operations.js; do
  test -f "$BACKUP/$f" && cp "$BACKUP/$f" "$ROOT/$f"
done
rm -f "$ROOT/backend/db/repositories/change_management_repository.py" "$ROOT/backend/services/change_management_service.py" "$ROOT/backend/modules/platform_change_management.py"
sudo systemctl restart nexus-api.service
echo "Package 045 application files rolled back from: $BACKUP"
echo "Migration 034 data was intentionally retained."
