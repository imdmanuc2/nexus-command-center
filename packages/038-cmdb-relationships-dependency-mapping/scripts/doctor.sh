#!/usr/bin/env bash
set -euo pipefail
PKG="$(cd "$(dirname "$0")/.." && pwd)"; ROOT="$(cd "$PKG/../.." && pwd)"
for f in backend/api/server.py frontend/assets.html frontend/js/assets.js backend/db/connection.py; do [[ -f "$ROOT/$f" ]] || { echo "Missing $f"; exit 1; }; done
python3 -m py_compile "$PKG/backend/api/server.py" "$PKG/backend/db/repositories/dependency_repository.py" "$PKG/backend/services/dependency_mapping_service.py" "$PKG/backend/modules/platform_dependencies.py"
echo "Package 038 doctor passed."
