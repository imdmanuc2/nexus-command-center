#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
cd "$ROOT"

test -f frontend/js/nav.js
test -f backend/data/private/cmdb.env

curl --max-time 10 -fsS \
  http://127.0.0.1:8080/api/platform/operations-center \
  | jq -e '.status == "ok"' >/dev/null

echo "Package 025 doctor passed."
