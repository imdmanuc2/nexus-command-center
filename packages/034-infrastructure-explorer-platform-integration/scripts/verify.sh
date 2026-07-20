#!/usr/bin/env bash
set -euo pipefail

PACKAGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="$(cd "$PACKAGE_DIR/../.." && pwd)"
GRAPH="$REPO_DIR/frontend/js/graph.js"
CLIENT="$REPO_DIR/frontend/js/nexus-platform-explorer.js"

pass() { printf '%-62s PASS\n' "$1"; }
check() { local label="$1" pattern="$2" file="$3"; grep -Fq "$pattern" "$file" && pass "$label" || { printf '%-62s FAIL\n' "$label"; exit 1; }; }
reject() { local label="$1" pattern="$2" file="$3"; if grep -Fq "$pattern" "$file"; then printf '%-62s FAIL\n' "$label"; exit 1; else pass "$label"; fi; }

echo "== Verify Package 034 =="
check "Canonical Platform topology endpoint" '/api/platform/topology' "$CLIENT"
check "Canonical Platform workers endpoint" '/api/platform/workers' "$CLIENT"
check "Eight-second Platform request timeout" 'REQUEST_TIMEOUT_MS = 8000' "$CLIENT"
check "Explicit Platform topology client usage" 'platform.getTopology()' "$GRAPH"
check "Explicit Platform worker client usage" 'platform.getWorkers()' "$GRAPH"
check "PostgreSQL Platform live indicator" 'Live · Platform' "$GRAPH"
check "Last-known-good worker telemetry retention" 'Preserve last-known-good worker telemetry' "$GRAPH"
check "Rebuild retained as reconciliation action" '/api/graph/rebuild' "$GRAPH"
reject "Global fetch interception removed" 'window.fetch = async function' "$CLIENT"
reject "Legacy topology data read removed" 'fetch(rebuild ? "/api/graph/rebuild" : "/api/graph/live")' "$GRAPH"
reject "Legacy worker data read removed" 'fetch("/api/mining/workers")' "$GRAPH"
node --check "$GRAPH" >/dev/null && pass "Graph JavaScript syntax"
node --check "$CLIENT" >/dev/null && pass "Platform client JavaScript syntax"

echo
echo "Package 034 verified."
