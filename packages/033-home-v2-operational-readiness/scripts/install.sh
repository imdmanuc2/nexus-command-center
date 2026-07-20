#!/usr/bin/env bash
set -euo pipefail

PACKAGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$PACKAGE_DIR/../.." && pwd)"
TARGET="$REPO_ROOT/frontend/js/home-v2.js"
PATCH="$PACKAGE_DIR/patch/home-v2.js"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$TARGET.before-package-033-$STAMP"

[[ -f "$TARGET" ]] || { echo "Missing target: $TARGET"; exit 1; }
[[ -f "$PATCH" ]] || { echo "Missing patch: $PATCH"; exit 1; }

node --check "$PATCH"
cp -p "$TARGET" "$BACKUP"
cp "$PATCH" "$TARGET"
node --check "$TARGET"

echo "Installed Home V2 operational-readiness hardening."
echo "Backup: ${BACKUP#$REPO_ROOT/}"
echo "Package 033 installed."
