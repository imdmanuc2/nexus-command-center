#!/usr/bin/env bash
set -euo pipefail
PACKAGE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$PACKAGE_DIR/../.." && pwd)"
TARGET="$REPO_ROOT/backend/db/repositories/worker_repository.py"
pass(){ printf '%-64s PASS\n' "$1"; }
echo "== Verify Package 0341 =="
grep -q "UPDATE nexus.workloads AS workload" "$TARGET"; pass "Workloads aligned to current worker session"
grep -q "relationship.relationship_type = 'uses-pool'" "$TARGET"; pass "Old uses-pool relationships reconciled"
grep -q "relationship.relationship_type = 'mines-on'" "$TARGET"; pass "Old mines-on relationships reconciled"
grep -q "relationship.source <> 'platform-topology-reconciliation'" "$TARGET"; pass "Canonical topology edges protected"
grep -q "worker.current_session = TRUE" "$TARGET"; pass "Current-session gating present"
grep -q "worker.activity_state IN ('active', 'idle')" "$TARGET"; pass "Activity-state gating present"
python3 -m py_compile "$TARGET"; pass "Python syntax"
echo
echo "Package 0341 verified."
