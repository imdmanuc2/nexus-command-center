#!/usr/bin/env bash
set -euo pipefail
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$PACKAGE_ROOT/../../.." && pwd)"
cd "$REPO_ROOT"
for f in frontend/cmdb-object.html frontend/js/cmdb-object.js frontend/css/cmdb-object.css backend/services/cmdb_object_service.py; do
  [[ -f "$f" ]] || { echo "FAIL: $f"; exit 1; }; echo "PASS: $f"
done
for f in payload/frontend/cmdb-object.html payload/frontend/js/cmdb-object.js payload/frontend/css/cmdb-object.css payload/backend/services/cmdb_object_service.py; do
  [[ -f "$PACKAGE_ROOT/$f" ]] || { echo "FAIL: $f"; exit 1; }; echo "PASS: $f"
done
echo "Doctor PASS"
