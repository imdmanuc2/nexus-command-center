#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"
cd "$REPO_ROOT"

for file in \
  frontend/home-v2.html \
  frontend/js/home-v2.js \
  frontend/css/home-v2.css \
  backend/services/dashboard_summary_service.py; do
  [[ -f "$file" ]] && pass "$file" || fail "$file"
done

for file in \
  "$PAYLOAD_ROOT/frontend/home-v2.html" \
  "$PAYLOAD_ROOT/frontend/js/home-v2.js" \
  "$PAYLOAD_ROOT/frontend/css/home-v2.css" \
  "$PAYLOAD_ROOT/docs/PRODUCT_PRINCIPLES.md"; do
  [[ -f "$file" ]] && pass "$file" || fail "$file"
done

node --check "$PAYLOAD_ROOT/frontend/js/home-v2.js" >/dev/null
pass "Mission Control JavaScript syntax"

grep -q 'id="missionControlSummary"' "$PAYLOAD_ROOT/frontend/home-v2.html" || fail "Mission Control summary markup"
grep -q 'Engineering &amp; Production Detail' "$PAYLOAD_ROOT/frontend/home-v2.html" || fail "progressive disclosure markup"
grep -q 'function renderMissionControlSummary' "$PAYLOAD_ROOT/frontend/js/home-v2.js" || fail "canonical Mission Control renderer"
grep -q 'mission-control-summary' "$PAYLOAD_ROOT/frontend/css/home-v2.css" || fail "Mission Control styling"
grep -q '/api/platform/dashboard-summary' "$PAYLOAD_ROOT/frontend/js/home-v2.js" || fail "canonical dashboard consumer"
pass "Mission Control package contract"

echo "Doctor PASS"
