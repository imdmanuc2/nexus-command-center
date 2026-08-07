#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
PAYLOAD="$SCRIPT_DIR/../payload"

for file in \
  "$ROOT/frontend/graph.html" \
  "$ROOT/frontend/js/graph.js" \
  "$PAYLOAD/frontend/graph.html" \
  "$PAYLOAD/frontend/js/graph.js"; do
  test -f "$file" || { echo "FAIL: ${file#$ROOT/}" >&2; exit 1; }
  echo "PASS: ${file#$ROOT/}"
done

command -v node >/dev/null || { echo "FAIL: node not found" >&2; exit 1; }
node --check "$PAYLOAD/frontend/js/graph.js"

echo "Doctor PASS"
