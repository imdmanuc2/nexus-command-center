#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"
TARGET="frontend/js/home-v2.js"

printf '\n== Verify Package 032 ==\n'

grep -q 'function normalizeOperationsTimeline' "$TARGET"
printf '%-55s PASS\n' 'Timeline normalization'

grep -q '"/api/platform/timeline/latest"' "$TARGET"
printf '%-55s PASS\n' 'Canonical Platform Timeline endpoint'

if grep -q '"/api/events/operations"' "$TARGET"; then
  printf '%-55s FAIL\n' 'Legacy operations events endpoint removed'
  exit 1
fi
printf '%-55s PASS\n' 'Legacy operations events endpoint removed'

node --check "$TARGET"
printf '%-55s PASS\n' 'JavaScript syntax'

python3 -m compileall -q backend/modules/platform_timeline.py backend/db/repositories/timeline_repository.py
printf '%-55s PASS\n' 'Timeline backend imports compile'

printf '\nPackage 032 verified.\n'
