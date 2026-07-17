#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
cd "$PROJECT_ROOT"
python3 - <<'PY'
from backend.db.connection import healthcheck
print(healthcheck())
PY
for f in asset worker pool workload relationship; do
  test -f "backend/db/repositories/${f}_repository.py" || {
    echo "Missing repository: $f"
    exit 1
  }
done
echo "Doctor passed."
