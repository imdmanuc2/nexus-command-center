#!/usr/bin/env bash
set -euo pipefail
PACKAGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$PACKAGE_DIR/../.." && pwd)"
test -f "$REPO_ROOT/backend/api/server.py"
test -f "$REPO_ROOT/backend/data/private/cmdb.env"
test -x /usr/bin/python3
command -v psql >/dev/null
command -v curl >/dev/null
command -v jq >/dev/null
/usr/bin/python3 - <<'PY'
import psycopg
print('psycopg import PASS')
PY
grep -q 'ThreadingHTTPServer' "$REPO_ROOT/backend/api/server.py"
grep -q 'def do_GET' "$REPO_ROOT/backend/api/server.py"
echo 'Package 049 doctor PASS'
