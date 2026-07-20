#!/usr/bin/env bash
set -euo pipefail

PACKAGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_DIR="$(cd "$PACKAGE_DIR/../.." && pwd)"
GRAPH="$REPO_DIR/frontend/js/graph.js"
CLIENT="$REPO_DIR/frontend/js/nexus-platform-explorer.js"

latest_backup() {
  ls -1t "$1".before-package-034-* 2>/dev/null | head -n 1 || true
}

GRAPH_BACKUP="$(latest_backup "$GRAPH")"
CLIENT_BACKUP="$(latest_backup "$CLIENT")"

[[ -n "$GRAPH_BACKUP" ]] || { echo "No Package 034 graph backup found." >&2; exit 1; }
[[ -n "$CLIENT_BACKUP" ]] || { echo "No Package 034 Platform client backup found." >&2; exit 1; }

cp "$GRAPH_BACKUP" "$GRAPH"
cp "$CLIENT_BACKUP" "$CLIENT"
node --check "$GRAPH" >/dev/null
node --check "$CLIENT" >/dev/null

echo "Package 034 rolled back using:"
echo "  $GRAPH_BACKUP"
echo "  $CLIENT_BACKUP"
