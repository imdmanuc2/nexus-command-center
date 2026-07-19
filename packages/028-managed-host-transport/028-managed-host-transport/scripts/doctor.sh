#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
cd "$ROOT"
command -v ssh >/dev/null
command -v python3 >/dev/null
test -f backend/data/private/cmdb.env
python3 - <<'PY'
from backend.capabilities.registry import get_capability_registry
items={x['capabilityId'] for x in get_capability_registry().describe()}
required={'host.identity','host.disk-usage','service.status','service.restart','service.journal'}
assert required <= items
PY
echo "Package 028 doctor passed."
