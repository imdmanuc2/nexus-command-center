#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PAYLOAD_ROOT="$PACKAGE_ROOT/payload"
REPO_ROOT="${NEXUS_REPO_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_ROOT="$REPO_ROOT/backups/package-056-cmdb-foundation-$STAMP"

[[ -d "$REPO_ROOT/.git" ]] || { echo "Repository not found: $REPO_ROOT" >&2; exit 1; }

mkdir -p "$BACKUP_ROOT/frontend/js" "$BACKUP_ROOT/frontend/css"
cp -a "$REPO_ROOT/frontend/assets.html" "$BACKUP_ROOT/frontend/assets.html"
cp -a "$REPO_ROOT/frontend/js/assets.js" "$BACKUP_ROOT/frontend/js/assets.js"
cp -a "$REPO_ROOT/frontend/js/nav.js" "$BACKUP_ROOT/frontend/js/nav.js"
cp -a "$REPO_ROOT/frontend/css/style.css" "$BACKUP_ROOT/frontend/css/style.css"

install -m 0644 "$PAYLOAD_ROOT/frontend/assets.html" "$REPO_ROOT/frontend/assets.html"
install -m 0644 "$PAYLOAD_ROOT/frontend/js/assets.js" "$REPO_ROOT/frontend/js/assets.js"
install -m 0644 "$PAYLOAD_ROOT/frontend/js/nav.js" "$REPO_ROOT/frontend/js/nav.js"
install -m 0644 "$PAYLOAD_ROOT/frontend/css/style.css" "$REPO_ROOT/frontend/css/style.css"

printf 'Package 056 installed.\nBackup: %s\n' "$BACKUP_ROOT"
