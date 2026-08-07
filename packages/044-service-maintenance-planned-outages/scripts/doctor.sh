#!/usr/bin/env bash
set -euo pipefail
PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(cd "$PKG_DIR/../.." && pwd)"
test -f "$ROOT/backend/api/server.py"
test -f "$ROOT/backend/db/repositories/maintenance_repository.py"
test -f "$ROOT/backend/services/maintenance_service.py"
test -f "$ROOT/backend/services/service_impact_service.py"
test -f "$ROOT/frontend/service-operations.html"
test -f "$ROOT/backend/data/private/cmdb.env"
grep -q "maintenance_windows" "$ROOT/backend/db/migrations/023_maintenance_windows.sql"
grep -q "business_service_members" "$ROOT/backend/db/migrations/031_business_service_membership_reconciliation.sql"
command -v psql >/dev/null
command -v python3 >/dev/null
command -v curl >/dev/null
echo "Package 044 doctor PASS"
