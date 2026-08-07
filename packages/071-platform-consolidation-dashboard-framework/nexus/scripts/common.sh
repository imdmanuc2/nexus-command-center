#!/usr/bin/env bash
set -euo pipefail
PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$PACKAGE_ROOT/../../.." && pwd)"
# Expected: repo/packages/071.../nexus -> repo
if [[ ! -d "$REPO_ROOT/frontend" || ! -d "$REPO_ROOT/backend" ]]; then
  echo "FAIL: unable to locate Nexus repository root at $REPO_ROOT" >&2
  exit 1
fi
