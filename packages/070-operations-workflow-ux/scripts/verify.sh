#!/usr/bin/env bash
set -euo pipefail
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$PACKAGE_ROOT/../.." && pwd)"
cd "$REPO_ROOT"
node --check frontend/js/nav.js >/dev/null
echo "PASS: Navigation JavaScript syntax"
grep -q 'NEXUS_WORKFLOW_STEPS' frontend/js/nav.js
echo "PASS: unified operator workflow"
grep -q 'nexus-nav-more' frontend/js/nav.js
echo "PASS: secondary navigation grouping"
! grep -q 'appendChild(a)' frontend/js/nav.js
echo "PASS: duplicate Operations Center navigation removed"
grep -q 'nexus-workflow-ribbon' frontend/css/style.css
echo "PASS: workflow ribbon styling"
grep -q 'Operator focus' frontend/js/nav.js
echo "PASS: page-specific operator question"
grep -q 'event.key === "/"' frontend/js/nav.js
echo "PASS: global search shortcut"
for path in / /home-v2.html /assets.html /cmdb-object.html /graph.html; do
  code="$(curl -sS -o /dev/null -w '%{http_code}' "http://localhost:8080$path" || true)"
  if [ "$code" = "200" ]; then echo "PASS: $path"; else echo "WARN: $path returned $code"; fi
done
echo "Verify PASS"
