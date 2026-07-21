#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
for f in backend/db/migrations/026_cmdb_lifecycle_integration.sql backend/api/server.py frontend/assets.html frontend/js/assets.js; do [[ -f "$f" ]] || { echo "Missing $f"; exit 1; }; done
command -v python3 >/dev/null; command -v psql >/dev/null
echo "Package 037 doctor passed."
