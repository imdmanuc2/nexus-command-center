#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
BACKUP="${1:-$(ls -dt "$REPO_ROOT"/backups/package-069-* 2>/dev/null | head -1)}"
test -n "$BACKUP" && test -d "$BACKUP" || { echo 'No Package 069 backup found.'; exit 1; }
cp "$BACKUP/frontend/cmdb-object.html" "$REPO_ROOT/frontend/cmdb-object.html"
cp "$BACKUP/frontend/js/cmdb-object.js" "$REPO_ROOT/frontend/js/cmdb-object.js"
cp "$BACKUP/frontend/css/cmdb-object.css" "$REPO_ROOT/frontend/css/cmdb-object.css"
sudo systemctl restart nexus-api.service || true
echo "Rollback PASS: $BACKUP"
