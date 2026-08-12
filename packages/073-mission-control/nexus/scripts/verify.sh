#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"
cd "$REPO_ROOT"

node --check frontend/js/home-v2.js >/dev/null
pass "Mission Control JavaScript syntax"

grep -q 'Nexus Mission Control' frontend/home-v2.html || fail "Mission Control title"
pass "Mission Control title"

grep -q 'id="missionControlSummary"' frontend/home-v2.html || fail "Mission Control summary"
pass "Mission Control canonical summary"

grep -q 'Needs Attention' frontend/home-v2.html || fail "Needs Attention section"
pass "Needs Attention hierarchy"

grep -q 'Operational Readiness' frontend/home-v2.html || fail "Operational Readiness section"
pass "Operational Readiness hierarchy"

grep -q 'Recent Activity' frontend/home-v2.html || fail "Recent Activity section"
pass "Recent Activity hierarchy"

grep -q 'Engineering &amp; Production Detail' frontend/home-v2.html || fail "Engineering detail disclosure"
pass "engineering detail progressive disclosure"

grep -q 'function arrangeMissionControl' frontend/js/home-v2.js || fail "Mission Control layout controller"
pass "Mission Control layout controller"

grep -q 'function renderMissionControlSummary' frontend/js/home-v2.js || fail "Mission Control summary renderer"
pass "Mission Control live summary renderer"

grep -q '/api/platform/dashboard-summary' frontend/js/home-v2.js || fail "canonical dashboard endpoint"
pass "canonical dashboard summary source"

grep -q 'One metric, one canonical source' docs/PRODUCT_PRINCIPLES.md || fail "Version 1 product principles"
pass "Version 1 product principles"

if curl -fsS http://localhost:8080/home-v2.html >/dev/null 2>&1; then
  pass "/home-v2.html"
else
  warn "/home-v2.html unavailable during local verification"
fi

if payload="$(curl -fsS http://localhost:8080/api/platform/dashboard-summary 2>/dev/null)"; then
  python3 - "$payload" <<'PY'
import json, sys
obj=json.loads(sys.argv[1])
if not isinstance(obj, dict):
    raise SystemExit("dashboard summary is not an object")
summary=obj.get("summary") or {}
workers=summary.get("workers") or {}
pools=summary.get("pools") or {}
nodes=obj.get("nodes") or {}

missing=[]

if "fleetHashrate" not in summary:
    missing.append("summary.fleetHashrate")
if "online" not in workers:
    missing.append("summary.workers.online")
if "online" not in pools:
    missing.append("summary.pools.online")
if "onlineCount" not in nodes:
    missing.append("nodes.onlineCount")

if missing:
    raise SystemExit(
        "missing canonical dashboard fields: " + ", ".join(missing)
    )

print(
    "PASS: live canonical Mission Control metrics "
    f"(miners={workers['online']}, "
    f"pools={pools['online']}, "
    f"nodes={nodes['onlineCount']})"
)
PY
else
  warn "dashboard summary API unavailable during local verification"
fi

echo "Verify PASS"
