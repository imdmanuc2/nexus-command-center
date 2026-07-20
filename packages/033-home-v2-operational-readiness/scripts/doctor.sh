#!/usr/bin/env bash
set -euo pipefail

PACKAGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$PACKAGE_DIR/../.." && pwd)"
TARGET="$REPO_ROOT/frontend/js/home-v2.js"
PATCH="$PACKAGE_DIR/patch/home-v2.js"

check() {
  local label="$1" path="$2"
  if [[ -f "$path" ]]; then printf '%-58s PASS\n' "$label"; else printf '%-58s FAIL\n' "$label"; exit 1; fi
}

check "Current Home V2 JavaScript" "$TARGET"
check "Package 033 Home V2 patch" "$PATCH"

command -v node >/dev/null 2>&1 || { echo "node command                                      FAIL"; exit 1; }
printf '%-58s PASS\n' "Node.js syntax checker"

node --check "$TARGET"
node --check "$PATCH"
printf '%-58s PASS\n' "Current and packaged JavaScript syntax"

grep -q '"/api/platform/home"' "$TARGET"
printf '%-58s PASS\n' "Canonical Platform Home endpoint present"

grep -q '"/api/platform/timeline/latest"' "$TARGET"
printf '%-58s PASS\n' "Canonical Platform Timeline endpoint present"

echo
echo "Package 033 doctor passed."
