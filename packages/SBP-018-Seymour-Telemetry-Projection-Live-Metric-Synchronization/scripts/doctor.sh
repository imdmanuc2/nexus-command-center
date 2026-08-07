#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-$HOME/Projects/Seymour/nexus-command-center}"
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

fail(){ echo "SBP-018 doctor: FAIL — $*" >&2; exit 1; }

[[ -d "$ROOT/.git" ]] || fail "Nexus repository not found"
[[ "$(git -C "$ROOT" branch --show-current)" == "feature/discovery-engine-v2" ]] || fail "Expected feature/discovery-engine-v2 branch"

for file in   backend/api/server.py   backend/api/seymour_registration_routes.py   backend/services/seymour_registration_service.py   backend/db/repositories/seymour_registration_repository.py   backend/data/private/cmdb.env; do
  [[ -f "$ROOT/$file" ]] || fail "Missing $file"
done

python3 -m py_compile   "$PKG/payload/backend/db/repositories/seymour_telemetry_repository.py"   "$PKG/payload/backend/services/seymour_telemetry_service.py"   "$PKG/payload/backend/api/seymour_telemetry_routes.py"   "$PKG/payload/patch_registration_repository.py"   "$PKG/payload/patch_server.py"

echo "SBP-018 doctor: PASS"
