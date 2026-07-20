#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
cd "$ROOT"

fail=0
for file in frontend/js/home-v2.js backend/modules/platform_timeline.py backend/api/server.py; do
  if [[ -f "$file" ]]; then
    printf '%-55s PASS\n' "$file"
  else
    printf '%-55s FAIL\n' "$file"
    fail=1
  fi
done

python3 --version >/dev/null
command -v node >/dev/null || {
  echo "node is required for JavaScript syntax verification"
  fail=1
}

if grep -q '"/api/platform/timeline/latest"' backend/api/server.py; then
  printf '%-55s PASS\n' 'Platform timeline route registered'
else
  printf '%-55s FAIL\n' 'Platform timeline route registered'
  fail=1
fi

exit "$fail"
