#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd)"
PAYLOAD="$SCRIPT_DIR/../payload"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$ROOT/backups/package-063-$STAMP"

mkdir -p "$BACKUP/frontend/js"
cp -a "$ROOT/frontend/graph.html" "$BACKUP/frontend/graph.html"
cp -a "$ROOT/frontend/js/graph.js" "$BACKUP/frontend/js/graph.js"
echo "Backup: $BACKUP"

install -m 0644 "$PAYLOAD/frontend/graph.html" "$ROOT/frontend/graph.html"
install -m 0644 "$PAYLOAD/frontend/js/graph.js" "$ROOT/frontend/js/graph.js"

sudo systemctl restart nexus-api.service
for _ in $(seq 1 30); do
  if curl -fsS http://localhost:8080/graph.html >/dev/null 2>&1; then
    echo "Install PASS"
    exit 0
  fi
  sleep 1
done

echo "FAIL: nexus-api.service did not become ready" >&2
exit 1
