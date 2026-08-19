#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"
cd "$REPO_ROOT"

[[ -f "$BACKUP_MARKER" ]] || fail "no Package 073 backup marker found"
BACKUP="$(cat "$BACKUP_MARKER")"
[[ -d "$BACKUP" ]] || fail "backup directory missing: $BACKUP"

cp "$BACKUP/frontend/home-v2.html" frontend/home-v2.html
cp "$BACKUP/frontend/js/home-v2.js" frontend/js/home-v2.js
cp "$BACKUP/frontend/css/home-v2.css" frontend/css/home-v2.css

if [[ -f "$BACKUP/docs/PRODUCT_PRINCIPLES.md" ]]; then
  mkdir -p docs
  cp "$BACKUP/docs/PRODUCT_PRINCIPLES.md" docs/PRODUCT_PRINCIPLES.md
else
  rm -f docs/PRODUCT_PRINCIPLES.md
fi

echo "Rollback PASS"
