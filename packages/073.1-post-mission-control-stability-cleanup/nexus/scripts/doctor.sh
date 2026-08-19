#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PAYLOAD="$PKG_ROOT/nexus/payload"

echo "Package 073.1 doctor: checking stability cleanup prerequisites"

FILES=(
  "$PAYLOAD/backend/api/server.py"
  "$PAYLOAD/backend/db/repositories/alert_repository.py"
  "$PAYLOAD/backend/db/repositories/recommendation_repository.py"
  "$PAYLOAD/backend/services/alert_engine_service.py"
)

for file in "${FILES[@]}"; do
  test -f "$file"
  echo "PASS: $file"
done

/usr/bin/python3 -m py_compile "${FILES[@]}"

echo "PASS: Python syntax"

grep -q 'static_path = urlparse(self.path).path' \
  "$PAYLOAD/backend/api/server.py"

grep -q '"reopened" if was_resolved else "updated"' \
  "$PAYLOAD/backend/db/repositories/alert_repository.py"

grep -q '"reopened"' \
  "$PAYLOAD/backend/db/repositories/recommendation_repository.py"

grep -q 'suppression_cache' \
  "$PAYLOAD/backend/services/alert_engine_service.py"

grep -q 'result in ("updated", "reopened")' \
  "$PAYLOAD/backend/services/alert_engine_service.py"

echo "Package 073.1 doctor: PASS"
