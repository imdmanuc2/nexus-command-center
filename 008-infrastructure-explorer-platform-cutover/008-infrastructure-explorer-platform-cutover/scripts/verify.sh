#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
BASE="${BASE:-http://127.0.0.1:8080}"
cd "$PROJECT_ROOT"
curl -fsS "$BASE/api/platform/topology" | jq '{status, source, counts}'
adapter_line="$(grep -n 'nexus-platform-explorer.js' frontend/graph.html | head -1 | cut -d: -f1)"
graph_line="$(grep -n 'graph.js' frontend/graph.html | head -1 | cut -d: -f1)"
[[ -n "$adapter_line" && -n "$graph_line" && "$adapter_line" -lt "$graph_line" ]]
curl -fsS "$BASE/js/nexus-platform-explorer.js" | grep -q 'nexus-postgresql-platform-explorer-adapter'
echo "Infrastructure Explorer Platform cutover verified."
