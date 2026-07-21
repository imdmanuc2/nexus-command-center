#!/usr/bin/env bash
set -euo pipefail
PKG="$(cd "$(dirname "$0")/.." && pwd)"; ROOT="$(cd "$PKG/../.." && pwd)"
command -v python3 >/dev/null; command -v psql >/dev/null; command -v curl >/dev/null
[[ -f "$ROOT/backend/api/server.py" ]] || { echo "Nexus repository root not found"; exit 1; }
python3 -m py_compile "$PKG/backend/api/server.py" "$PKG/backend/db/repositories/service_operations_repository.py" "$PKG/backend/services/service_operations_service.py" "$PKG/backend/modules/platform_service_operations.py"
grep -q '/api/services/topology' "$ROOT/backend/api/server.py" || { echo "Package 040 is required"; exit 1; }
echo "Package 041 doctor passed."
