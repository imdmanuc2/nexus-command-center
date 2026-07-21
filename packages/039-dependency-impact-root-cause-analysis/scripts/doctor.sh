#!/usr/bin/env bash
set -euo pipefail
PKG="$(cd "$(dirname "$0")/.." && pwd)"; ROOT="$(cd "$PKG/../.." && pwd)"
for f in backend/api/server.py backend/db/connection.py backend/db/repositories/dependency_repository.py frontend/js/assets.js; do [[ -f "$ROOT/$f" ]] || { echo "Missing $f"; exit 1; }; done
python3 -m py_compile "$PKG/backend/core/impact_engine.py" "$PKG/backend/core/root_cause_engine.py" "$PKG/backend/core/recommendation_engine.py" "$PKG/backend/services/intelligence_service.py"
echo "Package 039 doctor passed."
