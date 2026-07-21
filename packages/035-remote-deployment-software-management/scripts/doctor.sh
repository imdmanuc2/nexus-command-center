#!/usr/bin/env bash
set -euo pipefail
PKG="$(cd "$(dirname "$0")/.." && pwd)"; ROOT="$(cd "$PKG/../.." && pwd)"
for f in "$ROOT/backend/api/server.py" "$ROOT/backend/data/private/cmdb.env" "$PKG/backend/db/migrations/024_remote_deployments.sql"; do [ -f "$f" ] || { echo "Missing $f"; exit 1; }; done
command -v psql >/dev/null || { echo "psql is required"; exit 1; }
python3 -m py_compile "$PKG/backend/api/server.py" "$PKG/backend/services/deployment_service.py" "$PKG/backend/db/repositories/deployment_repository.py"
echo "Package 035 doctor passed."
