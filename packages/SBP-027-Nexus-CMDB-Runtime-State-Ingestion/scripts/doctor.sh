#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/home/imdmanuc/Projects/Seymour/nexus-command-center}"
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

fail() {
  echo "SBP-027 doctor: FAIL — $*" >&2
  exit 1
}

[[ -d "$ROOT/.git" ]] \
  || fail "Nexus repository not found"

[[ -f \
  "$ROOT/backend/db/repositories/seymour_registration_repository.py" ]] \
  || fail "Seymour registration repository not found"

grep -q "seymour_telemetry_repository" \
  "$ROOT/backend/db/repositories/seymour_registration_repository.py" \
  || fail "SBP-018 telemetry integration not found"

python3 -m py_compile \
  "$PKG/payload/backend/db/repositories/seymour_runtime_state_repository.py" \
  "$PKG/payload/patch_registration_repository.py"

echo "SBP-027 doctor: PASS"
