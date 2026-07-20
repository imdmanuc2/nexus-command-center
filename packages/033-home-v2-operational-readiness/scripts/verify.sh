#!/usr/bin/env bash
set -euo pipefail

PACKAGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$PACKAGE_DIR/../.." && pwd)"
TARGET="$REPO_ROOT/frontend/js/home-v2.js"

pass() { printf '%-58s PASS\n' "$1"; }
require() { grep -q "$2" "$TARGET" || { printf '%-58s FAIL\n' "$1"; exit 1; }; pass "$1"; }

echo "== Verify Package 033 =="
require "Eight-second request timeout" 'HOME_V2_REQUEST_TIMEOUT_MS = 8000'
require "Stale telemetry threshold" 'HOME_V2_STALE_AFTER_MS = 30000'
require "Critical stale telemetry threshold" 'HOME_V2_CRITICAL_STALE_AFTER_MS = 120000'
require "Guarded JSON request helper" 'async function fetchJson'
require "Last-known-good data retention" 'retaining last known data'
require "Repeated failure escalation" 'homeV2State.consecutiveFailures >= 3'
require "Visibility recovery refresh" '"visibilitychange"'
require "Online recovery refresh" 'window.addEventListener("online"'
require "Browser offline state" 'BROWSER OFFLINE'
require "Canonical Platform Home endpoint" '"/api/platform/home"'
require "Canonical Platform Timeline endpoint" '"/api/platform/timeline/latest"'

node --check "$TARGET"
pass "JavaScript syntax"

echo
echo "Package 033 verified."
