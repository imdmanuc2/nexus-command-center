#!/usr/bin/env bash
set -euo pipefail

HOTFIX_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(cd "$HOTFIX_DIR/../.." && pwd)"
TARGET="$ROOT/packages/047-change-rollback-orchestration-recovery-r3/scripts/verify.sh"

if [ ! -f "$TARGET" ]; then
  echo "Package 047 R3 verify script not found: $TARGET" >&2
  exit 1
fi

cp "$TARGET" "$TARGET.before-r3.1"
install -m 0755 "$HOTFIX_DIR/scripts/verify.sh" "$TARGET"

grep -q "rollback_capability" "$TARGET"
grep -q "host.identity" "$TARGET"
grep -q "target_id" "$TARGET"

echo "Package 047 R3.1 verification hotfix installed."
echo "Backup: $TARGET.before-r3.1"
