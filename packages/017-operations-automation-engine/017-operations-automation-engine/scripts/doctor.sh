#!/usr/bin/env bash
set -Eeuo pipefail
cd "${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
test -f backend/data/private/cmdb.env
curl -fsS http://127.0.0.1:8080/api/platform/recommendations | jq -e '.status == "ok"' >/dev/null
echo "Package 017 doctor passed."
