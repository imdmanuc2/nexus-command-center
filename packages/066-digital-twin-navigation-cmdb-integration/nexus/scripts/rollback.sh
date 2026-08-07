#!/usr/bin/env bash
set -euo pipefail
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$PACKAGE_ROOT/../../.." && pwd)"
LATEST="$(find "$REPO_ROOT/backups" -maxdepth 1 -type d -name 'package-066-*' | sort | tail -1)"
test -n "$LATEST" || { echo "No Package 066 backup found"; exit 1; }
cp -a "$LATEST/frontend/." "$REPO_ROOT/frontend/"
sudo systemctl restart nexus-api.service
echo "Rollback PASS: $LATEST"
