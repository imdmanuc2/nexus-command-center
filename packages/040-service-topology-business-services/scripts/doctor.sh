#!/usr/bin/env bash
set -euo pipefail
PKG="$(cd "$(dirname "$0")/.." && pwd)"; ROOT="$(cd "$PKG/../.." && pwd)"
for f in backend/api/server.py backend/db/connection.py backend/db/migrations/028_dependency_impact_root_cause_analysis.sql frontend/js/nav.js; do [[ -f "$ROOT/$f" ]] || { echo "Missing $f"; exit 1; }; done
python3 -m py_compile "$PKG/backend/db/repositories/service_topology_repository.py" "$PKG/backend/services/service_topology_service.py" "$PKG/backend/modules/platform_services.py" "$PKG/backend/api/server.py"
grep -q '/api/services/topology' "$PKG/backend/api/server.py"
echo "Package 040 doctor passed."
