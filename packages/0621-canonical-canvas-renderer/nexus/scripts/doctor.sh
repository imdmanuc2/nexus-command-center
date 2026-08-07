#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
PAYLOAD="$SCRIPT_DIR/../payload"

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
check_file "$PAYLOAD/frontend/js/graph.js"

node --check "$PAYLOAD/frontend/js/graph.js"
grep -q 'PACKAGE 062.1: canonical topology' "$PAYLOAD/frontend/js/graph.js"
grep -q 'function livePoolWorkers' "$PAYLOAD/frontend/js/graph.js"
grep -q 'ACCEPTING ·' "$PAYLOAD/frontend/js/graph.js"
echo "PASS: canonical Canvas renderer payload"

curl -fsS http://localhost:8080/api/platform/topology >/dev/null
echo "PASS: topology API reachable"
echo "Doctor PASS"
