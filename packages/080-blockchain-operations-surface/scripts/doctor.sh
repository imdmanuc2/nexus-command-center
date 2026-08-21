#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

test -f frontend/js/nav.js
test -f backend/api/server.py
test -f backend/db/repositories/asset_repository.py

python3 - <<'PY'
from backend.db.connection import get_connection

with get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) AS count
            FROM nexus.blockchain_nodes
        """)
        count = int(cur.fetchone()["count"])

assert count >= 1, "No canonical blockchain nodes found"

print(f"PASS: canonical blockchain nodes available ({count})")
PY

echo "PASS: Package 080 doctor"
