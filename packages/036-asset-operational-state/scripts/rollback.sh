#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"
if [ -f backups/package-036/server.py.before-036 ]; then cp -a backups/package-036/server.py.before-036 backend/api/server.py; fi
rm -f backend/db/repositories/operational_state_repository.py backend/services/operational_state_service.py backend/modules/platform_operational_state.py frontend/operational-state.html frontend/js/operational-state.js frontend/css/operational-state.css
echo "Code rollback complete. Database history was intentionally preserved."
