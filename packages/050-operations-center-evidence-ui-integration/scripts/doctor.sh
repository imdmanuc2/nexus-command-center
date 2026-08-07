#!/usr/bin/env bash
set -euo pipefail
P="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; R="$(cd "$P/../.." && pwd)"
test -d "$R/frontend"; test -f "$R/frontend/js/nav.js"; test -x /usr/bin/python3; command -v curl >/dev/null
curl -fsS http://localhost:8080/api/evidence/status | /usr/bin/python3 -c 'import json,sys; assert json.load(sys.stdin)["status"]=="ok"'
echo "Package 049 evidence API PASS"; echo "Package 050 doctor PASS"
