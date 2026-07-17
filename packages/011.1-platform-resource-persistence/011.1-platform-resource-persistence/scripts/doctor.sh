#!/usr/bin/env bash
set -Eeuo pipefail
cd "${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
test -f backend/data/private/cmdb.env
test -f backend/jobs/platform_sync_job.py
curl -fsS http://127.0.0.1:8080/api/blockchain/nodes | python3 -m json.tool >/dev/null
curl -fsS http://127.0.0.1:8080/api/connectors/status | jq -e '.connectors.miningcore' >/dev/null
echo 'Package 011.1 doctor passed.'
