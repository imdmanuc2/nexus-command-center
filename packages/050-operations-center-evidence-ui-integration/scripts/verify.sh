#!/usr/bin/env bash
set -euo pipefail
P="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; R="$(cd "$P/../.." && pwd)"; cd "$R"
test -f frontend/operations-center.html; test -f frontend/js/evidence-client.js; test -f frontend/js/operations-center.js; test -f frontend/css/operations-center.css; echo "operations center files PASS"
grep -q operations-center.html frontend/js/nav.js; echo "operations center navigation PASS"
grep -q /api/evidence frontend/js/evidence-client.js; grep -q /api/timeline/operations frontend/js/evidence-client.js; grep -q /api/recommendations/context frontend/js/evidence-client.js; echo "evidence client integration PASS"
grep -q 'id="opsTimeline"' frontend/operations-center.html; grep -q NexusEvidence.timeline frontend/js/operations-center.js; grep -q NexusEvidence.get frontend/js/operations-center.js; echo "operations center lifecycle PASS"
curl -fsS http://localhost:8080/operations-center.html | grep -q 'Operations Center'; curl -fsS http://localhost:8080/js/evidence-client.js | grep -q NexusEvidence; curl -fsS http://localhost:8080/css/operations-center.css | grep -q ops-shell; echo "operations center page PASS"
curl -fsS http://localhost:8080/api/evidence/status | /usr/bin/python3 -c 'import json,sys; assert json.load(sys.stdin)["status"]=="ok"'; curl -fsS http://localhost:8080/api/timeline/operations | /usr/bin/python3 -c 'import json,sys; assert json.load(sys.stdin)["status"]=="ok"'; echo "operations evidence APIs PASS"
if [[ -f frontend/home-v2.html ]]; then grep -q home-v2-evidence.css frontend/home-v2.html; grep -q home-v2-evidence.js frontend/home-v2.html; echo "Home V2 evidence integration PASS"; fi
echo "Package 050 verification PASS"
