#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/home/imdmanuc/Projects/Seymour/nexus-command-center}"
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

fail() {
  echo "SBP-029 doctor: FAIL — $*" >&2
  exit 1
}

[[ -d "$ROOT/.git" ]] || fail "Nexus repository not found"

for file in \
  frontend/assets.html \
  frontend/cmdb-object.html; do
  [[ -f "$ROOT/$file" ]] || fail "Missing $file"
done

python3 -m py_compile \
  "$PKG/payload/patch_cmdb_pages.py"

echo "SBP-029 doctor: PASS"
