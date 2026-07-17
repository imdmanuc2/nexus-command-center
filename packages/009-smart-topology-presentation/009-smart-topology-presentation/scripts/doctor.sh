#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
BASE="${BASE:-http://127.0.0.1:8080}"
cd "$PROJECT_ROOT"
command -v node >/dev/null
test -f frontend/js/graph.js
test -f frontend/js/nexus-platform-explorer.js
curl -fsS "$BASE/api/platform/topology" | jq -e '.status == "ok"' >/dev/null
echo "Package 009 doctor passed."
