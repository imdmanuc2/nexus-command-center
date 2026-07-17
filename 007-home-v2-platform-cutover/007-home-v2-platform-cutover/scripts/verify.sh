#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
BASE="${BASE:-http://127.0.0.1:8080}"
cd "$PROJECT_ROOT"
for endpoint in fleet pools workers; do
  curl -fsS "$BASE/api/platform/$endpoint" | jq -e '.status == "ok"' >/dev/null
done
adapter_line="$(grep -n 'nexus-platform-home.js' frontend/home-v2.html | head -1 | cut -d: -f1)"
home_line="$(grep -n 'home-v2.js' frontend/home-v2.html | head -1 | cut -d: -f1)"
[[ -n "$adapter_line" && -n "$home_line" && "$adapter_line" -lt "$home_line" ]]
curl -fsS "$BASE/js/nexus-platform-home.js" | grep -q 'nexus-postgresql-platform-home-adapter'
echo "Home v2 Platform API cutover verified."
