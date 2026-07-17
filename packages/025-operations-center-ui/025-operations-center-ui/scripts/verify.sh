#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
cd "$ROOT"

echo "== Operations Center page =="

curl --max-time 10 -fsS \
  http://127.0.0.1:8080/operations-center.html \
  >/tmp/package-025-page.html

grep -q "Nexus Operations Center" \
  /tmp/package-025-page.html

echo "/operations-center.html                        PASS"

echo
echo "== Static assets =="

for asset in \
  css/operations-center.css \
  js/operations-center.js \
  js/nav.js
do
  printf '%-48s ' "/$asset"
  curl --max-time 10 -fsS \
    "http://127.0.0.1:8080/$asset" \
    >/dev/null
  echo PASS
done

echo
echo "== Operations Center API =="

curl --max-time 10 -fsS \
  http://127.0.0.1:8080/api/platform/operations-center \
  >/tmp/package-025-dashboard.json

jq '{
    status,
    source,
    generatedAt,
    overall,
    infrastructure: {
      workers: .infrastructure.workers,
      topology: .infrastructure.topology,
      workerCountMatchesTopology:
        .infrastructure.workerCountMatchesTopology
    },
    alerts: .alerts.summary,
    recommendations: .recommendations.summary,
    operations: .operations.summary,
    timeline: .timeline.summary
  }' /tmp/package-025-dashboard.json

jq -e '
  .status == "ok"
  and (.overall.healthScore >= 0)
  and (.overall.healthScore <= 100)
  and (
    .infrastructure.workerCountMatchesTopology
    == true
  )
' /tmp/package-025-dashboard.json \
  >/dev/null

echo
echo "== Navigation registration =="

grep -n \
  'Operations Center' \
  frontend/js/nav.js

echo "Package 025 verified."
