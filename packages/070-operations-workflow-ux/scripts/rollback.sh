#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$PACKAGE_ROOT/../.." && pwd)"
LATEST="$(ls -dt "$REPO_ROOT"/backups/package-070-* 2>/dev/null | head -1 || true)"
[ -n "$LATEST" ] || { echo "No Package 070 backup found"; exit 1; }
cp -a "$LATEST/frontend/." "$REPO_ROOT/frontend/"
sudo systemctl restart nexus-api.service || true
echo "Rollback PASS: $LATEST"
