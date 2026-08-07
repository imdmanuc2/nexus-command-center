#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-$HOME/Projects/Seymour/nexus-command-center}"
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

fail() {
  echo "SBP-017 doctor: FAIL — $*" >&2
  exit 1
}

[[ -d "$ROOT/.git" ]] || fail "Nexus repository not found: $ROOT"

[[ "$(git -C "$ROOT" branch --show-current)" == "feature/discovery-engine-v2" ]] \
  || fail "Expected feature/discovery-engine-v2 branch"

for file in \
  backend/api/server.py \
  backend/db/connection.py \
  backend/db/migrations/001_nexus_platform_foundation.sql \
  backend/data/private/cmdb.env; do
  [[ -f "$ROOT/$file" ]] || fail "Missing $file"
done

grep -q "def do_GET" "$ROOT/backend/api/server.py" || fail "do_GET missing"
grep -q "def do_POST" "$ROOT/backend/api/server.py" || fail "do_POST missing"

python3 -m py_compile \
  "$PKG/payload/backend/db/repositories/seymour_registration_repository.py" \
  "$PKG/payload/backend/services/seymour_registration_service.py" \
  "$PKG/payload/backend/api/seymour_registration_routes.py" \
  "$PKG/payload/patch_server.py"

echo "SBP-017 doctor: PASS"
