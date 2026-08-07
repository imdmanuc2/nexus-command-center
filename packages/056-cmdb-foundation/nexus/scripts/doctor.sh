#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="${NEXUS_REPO_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"

pass(){ printf 'PASS  %s\n' "$1"; }
fail(){ printf 'FAIL  %s\n' "$1"; exit 1; }

[[ -d "$REPO_ROOT/.git" ]] && pass "Nexus repository detected" || fail "Repository not found at $REPO_ROOT"
[[ -f "$REPO_ROOT/frontend/assets.html" ]] && pass "Current Assets page detected" || fail "frontend/assets.html missing"
[[ -f "$REPO_ROOT/frontend/js/assets.js" ]] && pass "Current Assets JavaScript detected" || fail "frontend/js/assets.js missing"
[[ -f "$REPO_ROOT/frontend/js/nav.js" ]] && pass "Shared navigation detected" || fail "frontend/js/nav.js missing"
[[ -f "$PACKAGE_ROOT/payload/frontend/assets.html" ]] && pass "CMDB payload detected" || fail "Package payload missing"
command -v python3 >/dev/null && pass "Python runtime detected" || fail "python3 is required"

echo "Package 056 doctor PASS"
