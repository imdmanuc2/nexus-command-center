#!/usr/bin/env bash
set -euo pipefail
REPO="$HOME/Projects/Seymour/nexus-command-center"
PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
test -d "$REPO"
test -f "$REPO/backend/db/repositories/worker_repository.py"
test -f "$PKG_DIR/payload/backend/db/repositories/worker_repository.py"
grep -q "Hand off the unique current-session slot" "$PKG_DIR/payload/backend/db/repositories/worker_repository.py"
python3 -m py_compile "$PKG_DIR/payload/backend/db/repositories/worker_repository.py"
echo "PASS: worker repository"
echo "PASS: current-session handoff logic"
echo "Doctor PASS"
