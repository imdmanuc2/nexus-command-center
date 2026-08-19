#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
PAYLOAD="$PKG_ROOT/nexus/payload"

REPO="$(git -C "$SCRIPT_DIR" rev-parse --show-toplevel)"

echo "Package 073.1 verify: Post-Mission-Control stability cleanup"

FILES=(
  "backend/api/server.py"
  "backend/db/repositories/alert_repository.py"
  "backend/db/repositories/recommendation_repository.py"
  "backend/services/alert_engine_service.py"
)

for relative in "${FILES[@]}"; do
  test -f "$REPO/$relative"
  test -f "$PAYLOAD/$relative"

  SRC="$(sha256sum "$REPO/$relative" | awk '{print $1}')"
  PKG="$(sha256sum "$PAYLOAD/$relative" | awk '{print $1}')"

  test "$SRC" = "$PKG"

  echo "PASS: $relative payload checksum"
done

/usr/bin/python3 -m py_compile \
  "$REPO/backend/api/server.py" \
  "$REPO/backend/db/repositories/alert_repository.py" \
  "$REPO/backend/db/repositories/recommendation_repository.py" \
  "$REPO/backend/services/alert_engine_service.py"

echo "PASS: Python syntax"

grep -q 'static_path = urlparse(self.path).path' \
  "$REPO/backend/api/server.py"

echo "PASS: cache-busting static asset routing"

grep -q "status = 'open'" \
  "$REPO/backend/db/repositories/alert_repository.py"

grep -q '"reopened" if was_resolved else "updated"' \
  "$REPO/backend/db/repositories/alert_repository.py"

echo "PASS: alert reopen contract"

grep -q "status = 'open'" \
  "$REPO/backend/db/repositories/recommendation_repository.py"

grep -q '"reopened"' \
  "$REPO/backend/db/repositories/recommendation_repository.py"

echo "PASS: recommendation reopen contract"

grep -q 'suppression_cache' \
  "$REPO/backend/services/alert_engine_service.py"

grep -q 'matching_rules' \
  "$REPO/backend/services/alert_engine_service.py"

grep -q 'result in ("updated", "reopened")' \
  "$REPO/backend/services/alert_engine_service.py"

echo "PASS: alert-engine suppression/reopen contract"

echo "Package 073.1 verify: PASS"
