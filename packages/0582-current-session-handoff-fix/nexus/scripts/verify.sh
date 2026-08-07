#!/usr/bin/env bash
set -euo pipefail
REPO="$HOME/Projects/Seymour/nexus-command-center"
cd "$REPO"
python3 -m backend.jobs.platform_sync_job
python3 - <<'PY'
from backend.db.connection import get_connection

with get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT asset_id, COUNT(*) AS count
            FROM nexus.workers
            WHERE current_session = TRUE
              AND asset_id IS NOT NULL
            GROUP BY asset_id
            HAVING COUNT(*) > 1
        """)
        duplicates = cur.fetchall()
        assert not duplicates, f"duplicate current sessions: {duplicates}"

        cur.execute("""
            SELECT worker_id, asset_id, pool_instance_id, source_system,
                   current_session, activity_state, current_hashrate
            FROM nexus.workers
            WHERE source_system = 'seymour-native-stratum'
              AND current_session = TRUE
            ORDER BY worker_id
        """)
        rows = cur.fetchall()
        assert len(rows) == 2, f"expected 2 current Seymour workers, got {len(rows)}"
        assert all(r['asset_id'] for r in rows), rows
        assert all(r['pool_instance_id'] == 'seymour-btc-solo' for r in rows), rows
        assert all(r['activity_state'] == 'active' for r in rows), rows
        print("PASS: current Seymour workers 2")
        print("PASS: Seymour workers matched to assets")
        print("PASS: one current session per physical asset")

        cur.execute("""
            SELECT COUNT(*) AS count
            FROM nexus.workers
            WHERE current_session = TRUE
              AND source_system IN ('miningcore', 'generic-stratum')
              AND asset_id IN (
                  SELECT asset_id FROM nexus.workers
                  WHERE source_system = 'seymour-native-stratum'
                    AND current_session = TRUE
              )
        """)
        assert cur.fetchone()['count'] == 0
        print("PASS: displaced MiningCore and CKPool sessions retired")
PY
curl -fsS http://localhost:8080/api/platform/topology >/dev/null
echo "PASS: /api/platform/topology"
echo "Verify PASS"
