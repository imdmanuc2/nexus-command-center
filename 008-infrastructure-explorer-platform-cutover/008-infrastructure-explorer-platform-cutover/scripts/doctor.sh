#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
BASE="${BASE:-http://127.0.0.1:8080}"
cd "$PROJECT_ROOT"
test -f frontend/graph.html
test -f frontend/js/graph.js
curl -fsS "$BASE/api/platform/topology" | jq -e '.status == "ok" and (.counts.nodes > 0)' >/dev/null
curl -fsS "$BASE/api/platform/workers" | jq -e '.status == "ok"' >/dev/null
echo "Package 008 doctor passed."
