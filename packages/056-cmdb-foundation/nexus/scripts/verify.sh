#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="${NEXUS_REPO_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
HTML="$REPO_ROOT/frontend/assets.html"
JS="$REPO_ROOT/frontend/js/assets.js"
NAV="$REPO_ROOT/frontend/js/nav.js"
CSS="$REPO_ROOT/frontend/css/style.css"

check(){ grep -Fq "$2" "$1" && printf 'PASS  %s\n' "$3" || { printf 'FAIL  %s\n' "$3"; exit 1; }; }

check "$HTML" '<title>Nexus CMDB</title>' "CMDB browser title"
check "$HTML" '<h1>Nexus CMDB</h1>' "CMDB page heading"
check "$HTML" 'data-section="pools"' "CMDB pool section"
check "$HTML" 'data-section="relationships"' "CMDB relationship section"
check "$HTML" 'renderNav("CMDB")' "CMDB active navigation"
check "$NAV" '["CMDB", "/assets.html"]' "Assets navigation renamed to CMDB"
check "$JS" '/api/platform/inventory' "PostgreSQL platform inventory source"
check "$JS" 'PostgreSQL CMDB · authoritative' "Authoritative CMDB source indicator"
check "$JS" '/api/platform/pools' "Platform pool integration"
check "$JS" '/api/platform/relationships' "Platform relationship integration"
check "$CSS" 'Package 056: CMDB foundation' "CMDB foundation styling"

if command -v node >/dev/null 2>&1; then
  node --check "$JS"
  node --check "$NAV"
  echo "PASS  JavaScript syntax"
else
  echo "SKIP  JavaScript syntax (node not installed)"
fi

python3 - <<PY
from pathlib import Path
html = Path("$HTML").read_text()
required = ["overview", "assets", "pools", "nodes", "services", "workloads", "relationships", "discovery", "audit"]
missing = [name for name in required if f'data-panel="{name}"' not in html]
if missing:
    raise SystemExit(f"Missing CMDB panels: {missing}")
print("PASS  All CMDB panels present")
PY

echo "Package 056 verify PASS"
