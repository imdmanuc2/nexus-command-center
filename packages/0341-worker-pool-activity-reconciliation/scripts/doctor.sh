#!/usr/bin/env bash
set -euo pipefail
PACKAGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$PACKAGE_DIR/../.." && pwd)"
pass(){ printf '%-64s PASS\n' "$1"; }
[[ -f "$REPO_ROOT/backend/db/repositories/worker_repository.py" ]] || { echo "Missing worker_repository.py"; exit 1; }
pass "Current worker repository"
[[ -f "$PACKAGE_DIR/patch/backend/db/repositories/worker_repository.py" ]] || { echo "Missing packaged patch"; exit 1; }
pass "Packaged worker repository"
python3 -m py_compile "$PACKAGE_DIR/patch/backend/db/repositories/worker_repository.py"
pass "Packaged Python syntax"
grep -q "relationship.relationship_type = 'uses-pool'" "$PACKAGE_DIR/patch/backend/db/repositories/worker_repository.py"
pass "Workload pool relationship reconciliation"
grep -q "platform-topology-reconciliation" "$PACKAGE_DIR/patch/backend/db/repositories/worker_repository.py"
pass "Canonical topology relationship protection"
echo
echo "Package 0341 doctor passed."
