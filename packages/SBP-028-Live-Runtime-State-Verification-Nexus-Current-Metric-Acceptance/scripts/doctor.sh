#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/home/imdmanuc/Projects/Seymour/nexus-command-center}"
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

fail() {
  echo "SBP-028 doctor: FAIL — $*" >&2
  exit 1
}

[[ -d "$ROOT/.git" ]] \
  || fail "Nexus repository not found"

[[ -f \
  "$ROOT/backend/db/repositories/seymour_runtime_state_repository.py" ]] \
  || fail "SBP-027 runtime-state repository not found"

[[ -f \
  "$ROOT/backend/db/repositories/seymour_registration_repository.py" ]] \
  || fail "Seymour registration repository not found"

[[ -f "$ROOT/backend/data/private/cmdb.env" ]] \
  || fail "Nexus CMDB environment file not found"

python3 -m py_compile \
  "$PKG/payload/verify_live_runtime_state.py"

echo "SBP-028 doctor: PASS"
