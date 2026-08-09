#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/home/imdmanuc/Projects/Seymour/nexus-command-center}"
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

"$PKG/scripts/doctor.sh" "$ROOT"

cd "$ROOT"

mkdir -p tests

cp \
  "$PKG/payload/test_sbp028_contract.py" \
  tests/test_sbp028_contract.py

mkdir -p scripts/acceptance

cp \
  "$PKG/payload/verify_live_runtime_state.py" \
  scripts/acceptance/verify_sbp028_live_runtime_state.py

chmod +x \
  scripts/acceptance/verify_sbp028_live_runtime_state.py

echo "SBP-028 acceptance verifier installed."
echo "SBP-028 install: PASS"
echo "No service was restarted."
