#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
BACKUP="${1:-}"

if [[ -z "$BACKUP" || ! -d "$BACKUP" ]]; then
  echo "Usage: $0 /path/to/package-063-backup" >&2
  exit 1
fi

install -m 0644 "$BACKUP/frontend/graph.html" "$ROOT/frontend/graph.html"
install -m 0644 "$BACKUP/frontend/js/graph.js" "$ROOT/frontend/js/graph.js"
sudo systemctl restart nexus-api.service
echo "Rollback PASS"
