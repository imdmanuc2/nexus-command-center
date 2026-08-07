#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"

check_file() {
  local path="$1"
  if [[ -f "$path" ]]; then
    echo "PASS: ${path#$ROOT/}"
  else
    echo "FAIL: ${path#$ROOT/}" >&2
    exit 1
  fi
}

check_file "$ROOT/frontend/js/graph.js"
check_file "$PKG_ROOT/payload/frontend/js/graph.js"

node --check "$PKG_ROOT/payload/frontend/js/graph.js"
grep -q 'function canvasCanonicalLiveEdges' "$PKG_ROOT/payload/frontend/js/graph.js"
grep -q 'worker.currentSession !== true' "$PKG_ROOT/payload/frontend/js/graph.js"
grep -q 'replaceAll("-", "_")' "$PKG_ROOT/payload/frontend/js/graph.js"

echo "PASS: canonical live edge renderer"
echo "Doctor PASS"
