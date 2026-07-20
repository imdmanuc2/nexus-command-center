#!/usr/bin/env bash
set -euo pipefail

PACKAGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="$(cd "$PACKAGE_DIR/../.." && pwd)"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"

TARGET_GRAPH="$REPO_DIR/frontend/js/graph.js"
TARGET_CLIENT="$REPO_DIR/frontend/js/nexus-platform-explorer.js"

[[ -f "$TARGET_GRAPH" ]] || { echo "Missing $TARGET_GRAPH" >&2; exit 1; }
[[ -f "$TARGET_CLIENT" ]] || { echo "Missing $TARGET_CLIENT" >&2; exit 1; }

cp "$TARGET_GRAPH" "$TARGET_GRAPH.before-package-034-$TIMESTAMP"
cp "$TARGET_CLIENT" "$TARGET_CLIENT.before-package-034-$TIMESTAMP"

install -m 0644 "$PACKAGE_DIR/patch/frontend/js/graph.js" "$TARGET_GRAPH"
install -m 0644 "$PACKAGE_DIR/patch/frontend/js/nexus-platform-explorer.js" "$TARGET_CLIENT"

node --check "$TARGET_GRAPH" >/dev/null
node --check "$TARGET_CLIENT" >/dev/null

echo "Installed Infrastructure Explorer Platform integration."
echo "Backups:"
echo "  $TARGET_GRAPH.before-package-034-$TIMESTAMP"
echo "  $TARGET_CLIENT.before-package-034-$TIMESTAMP"
echo "Package 034 installed."
