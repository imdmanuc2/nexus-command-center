#!/usr/bin/env bash
set -euo pipefail

PACKAGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$PACKAGE_DIR/../.." && pwd)"
TARGET="$REPO_ROOT/frontend/js/home-v2.js"
BACKUP="$(ls -1t "$TARGET".before-package-033-* 2>/dev/null | head -n 1 || true)"

[[ -n "$BACKUP" ]] || { echo "No Package 033 backup found."; exit 1; }
cp "$BACKUP" "$TARGET"
node --check "$TARGET"
echo "Rolled back using: ${BACKUP#$REPO_ROOT/}"
