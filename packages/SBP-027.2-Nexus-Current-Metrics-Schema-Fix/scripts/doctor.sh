#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-/home/imdmanuc/Projects/Seymour/nexus-command-center}"
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ -d "$ROOT/.git" ]] || { echo "SBP-027.2 doctor: FAIL — Nexus repository not found"; exit 1; }
for file in backend/db/repositories/seymour_runtime_state_repository.py backend/db/repositories/seymour_telemetry_repository.py scripts/acceptance/verify_sbp028_live_runtime_state.py; do
  [[ -f "$ROOT/$file" ]] || { echo "SBP-027.2 doctor: FAIL — missing $file"; exit 1; }
done
python3 -m py_compile "$PKG/payload/replace_runtime_state_repository.py" "$PKG/payload/patch_sbp028_acceptance.py"
echo "SBP-027.2 doctor: PASS"
