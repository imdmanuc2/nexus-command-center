#!/usr/bin/env bash
set -euo pipefail
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$PACKAGE_ROOT/../../.." && pwd)"
LATEST="$(find "$REPO_ROOT/backups" -maxdepth 1 -type d -name 'package-068-*' | sort | tail -1)"
[[ -n "$LATEST" ]] || { echo "No Package 068 backup found."; exit 1; }
cp "$LATEST/frontend/assets.html" "$REPO_ROOT/frontend/assets.html"
cp "$LATEST/frontend/js/assets.js" "$REPO_ROOT/frontend/js/assets.js"
cp "$LATEST/frontend/css/style.css" "$REPO_ROOT/frontend/css/style.css"
if command -v sudo >/dev/null 2>&1; then sudo systemctl restart nexus-api.service || true; fi
echo "Rollback PASS: $LATEST"
