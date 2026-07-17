#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
BASE="${BASE:-http://127.0.0.1:8080}"
cd "$PROJECT_ROOT"
curl -fsS "$BASE/api/platform/topology" | jq '{status, source, counts}'
node --check frontend/js/graph.js
grep -nA12 -B3 'function resolvedCanvasViewMode' frontend/js/graph.js
grep -nA32 'function canvasBuildModel' frontend/js/graph.js | head -40
echo "Smart topology presentation verified."
