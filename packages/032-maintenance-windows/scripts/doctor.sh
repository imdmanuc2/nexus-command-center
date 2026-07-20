#!/usr/bin/env bash
set -euo pipefail
PKG="$(cd "$(dirname "$0")/.." && pwd)"; ROOT="$(cd "$PKG/../.." && pwd)"; cd "$ROOT"
command -v python3 >/dev/null; command -v psql >/dev/null; command -v zip >/dev/null || true
[ -f backend/db/migrations/022_lightweight_policy_engine.sql ]
[ -f backend/services/alert_engine_service.py ]
[ -f backend/db/repositories/audit_repository.py ]
python3 -m py_compile "$PKG/backend/db/repositories/maintenance_repository.py" "$PKG/backend/services/maintenance_service.py" "$PKG/backend/modules/platform_maintenance.py" "$PKG/backend/services/alert_engine_service.py" "$PKG/backend/api/server.py"
echo "Package 032 doctor passed."
