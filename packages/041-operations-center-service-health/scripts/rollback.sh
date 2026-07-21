#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
BACKUP="$(find "$ROOT/packages/backups" -maxdepth 1 -type d -name '041-operations-center-service-health-*' | sort | tail -1)"
[[ -n "$BACKUP" ]] || { echo "No Package 041 backup found"; exit 1; }
[[ -f "$BACKUP/backend/api/server.py" ]] && cp "$BACKUP/backend/api/server.py" "$ROOT/backend/api/server.py"
[[ -f "$BACKUP/frontend/js/nav.js" ]] && cp "$BACKUP/frontend/js/nav.js" "$ROOT/frontend/js/nav.js"
rm -f "$ROOT/backend/db/repositories/service_operations_repository.py" "$ROOT/backend/services/service_operations_service.py" "$ROOT/backend/modules/platform_service_operations.py" "$ROOT/frontend/service-operations.html" "$ROOT/frontend/css/service-operations.css" "$ROOT/frontend/js/service-operations.js"
sudo systemctl restart nexus-api.service
echo "Package 041 application files rolled back. Database tables were retained for safety."
