#!/usr/bin/env bash
set -euo pipefail

ROOT="$(
  cd "$(dirname "${BASH_SOURCE[0]}")/../../.." &&
  pwd
)"

for file in \
  "$ROOT/frontend/blockchain.html" \
  "$ROOT/frontend/js/blockchain.js" \
  "$ROOT/frontend/css/blockchain.css"
do
  test -f "$file"
  echo "PASS: $(realpath --relative-to="$ROOT" "$file")"
done

grep -q 'id="topNav"' \
  "$ROOT/frontend/blockchain.html"

grep -q 'overallState' \
  "$ROOT/frontend/js/blockchain.js"

grep -q 'runtimeState' \
  "$ROOT/frontend/js/blockchain.js"

grep -q 'connectivityState' \
  "$ROOT/frontend/js/blockchain.js"

grep -q 'syncState' \
  "$ROOT/frontend/js/blockchain.js"

grep -q 'rpcState' \
  "$ROOT/frontend/js/blockchain.js"

grep -q 'miningReadiness' \
  "$ROOT/frontend/js/blockchain.js"

echo "PASS: canonical UI contract"
