#!/usr/bin/env bash
set -euo pipefail

PACKAGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="$(cd "$PACKAGE_DIR/../.." && pwd)"

pass() { printf '%-62s PASS\n' "$1"; }
fail() { printf '%-62s FAIL\n' "$1"; exit 1; }

[[ -f "$REPO_DIR/frontend/js/graph.js" ]] && pass "Current Infrastructure Explorer graph JavaScript" || fail "Current Infrastructure Explorer graph JavaScript"
[[ -f "$REPO_DIR/frontend/js/nexus-platform-explorer.js" ]] && pass "Current Platform Explorer adapter" || fail "Current Platform Explorer adapter"
[[ -f "$PACKAGE_DIR/patch/frontend/js/graph.js" ]] && pass "Packaged graph JavaScript" || fail "Packaged graph JavaScript"
[[ -f "$PACKAGE_DIR/patch/frontend/js/nexus-platform-explorer.js" ]] && pass "Packaged Platform Explorer client" || fail "Packaged Platform Explorer client"
command -v node >/dev/null 2>&1 && pass "Node.js syntax checker" || fail "Node.js syntax checker"
node --check "$PACKAGE_DIR/patch/frontend/js/graph.js" >/dev/null && pass "Packaged graph JavaScript syntax" || fail "Packaged graph JavaScript syntax"
node --check "$PACKAGE_DIR/patch/frontend/js/nexus-platform-explorer.js" >/dev/null && pass "Packaged Platform client syntax" || fail "Packaged Platform client syntax"
grep -q 'src="/js/nexus-platform-explorer.js"' "$REPO_DIR/frontend/graph.html" && pass "Platform client loaded by graph page" || fail "Platform client loaded by graph page"
grep -q 'src="/js/graph.js"' "$REPO_DIR/frontend/graph.html" && pass "Graph JavaScript loaded by graph page" || fail "Graph JavaScript loaded by graph page"

echo
echo "Package 034 doctor passed."
