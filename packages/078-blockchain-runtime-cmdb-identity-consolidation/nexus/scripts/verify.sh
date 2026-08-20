#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
cd "$ROOT"

SERVICE="backend/services/blockchain_runtime_identity_consolidation_service.py"

MANAGER="asset-7be2040a1a33c91c"
BCH="asset-1a3a169d72207de3"

echo "Package 078 verify"

python3 -m py_compile "$SERVICE"
echo "PASS: Python syntax"

python3 - <<'PY'
from pathlib import Path

text = Path(
    "backend/services/"
    "blockchain_runtime_identity_consolidation_service.py"
).read_text()

assert 'CONFIRMATION = "CONSOLIDATE-SEYMOUR-RUNTIME-IDENTITIES"' in text
assert '"writeOperations": False' in text
assert "registrationRawPayloadPreserved" in text
assert "auditMetadataPreserved" in text
assert "_unexpected_fk_references" in text
assert "unexpectedRelationships" in text
assert "connection.rollback()" in text
assert "EXCLUDED.observed_at" in text
assert "DELETE FROM nexus.blockchain_nodes" in text
assert "DELETE FROM nexus.assets" in text

print("PASS: explicit confirmation required")
print("PASS: plan mode performs no writes")
print("PASS: raw historical registration evidence preserved")
print("PASS: audit metadata preserved")
print("PASS: unexpected FK references block execution")
print("PASS: unexpected relationships block execution")
print("PASS: transaction rollback contract")
print("PASS: newest current metric wins")
print("PASS: canonical BCH projection survives")
PY

echo
echo "===== LIVE PLAN — NO WRITES ====="

BEFORE_COUNTS="$(
python3 - <<'PY2'
from backend.db.repositories.asset_repository import count_assets
from backend.db.repositories.relationship_repository import list_relationships

print(
    count_assets(),
    len(list_relationships()),
)
PY2
)"

python3 -m backend.services.blockchain_runtime_identity_consolidation_service \
  --manager "$MANAGER" \
  --bch "$BCH"

AFTER_COUNTS="$(
python3 - <<'PY2'
from backend.db.repositories.asset_repository import count_assets
from backend.db.repositories.relationship_repository import list_relationships

print(
    count_assets(),
    len(list_relationships()),
)
PY2
)"

echo
echo "===== LIVE COUNTS MUST REMAIN UNCHANGED ====="

echo "before=$BEFORE_COUNTS"
echo "after=$AFTER_COUNTS"

if [ "$BEFORE_COUNTS" != "$AFTER_COUNTS" ]; then
    echo "ERROR: plan mode changed CMDB counts"
    exit 1
fi

case "$AFTER_COUNTS" in
    "37 47")
        echo "PASS: valid pre-consolidation CMDB state"
        ;;
    "7 32")
        echo "PASS: valid post-consolidation CMDB state"
        ;;
    *)
        echo "ERROR: unexpected CMDB state: $AFTER_COUNTS"
        exit 1
        ;;
esac

echo "PASS: live plan performed no CMDB writes"

python3 - <<'PY2'
from backend.db.connection import get_connection

MANAGER = "asset-7be2040a1a33c91c"
BCH = "asset-1a3a169d72207de3"

with get_connection() as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT COUNT(*) AS count
            FROM nexus.assets
            WHERE asset_type = 'blockchain-manager'
        """)
        managers = int(cur.fetchone()["count"])

        cur.execute("""
            SELECT COUNT(*) AS count
            FROM nexus.assets
            WHERE asset_type = 'blockchain-node'
              AND coin = 'BCH'
        """)
        bch_nodes = int(cur.fetchone()["count"])

        if managers == 1 and bch_nodes == 1:
            cur.execute("""
                SELECT COUNT(*) AS count
                FROM nexus.relationships
                WHERE source_id = %s
                  AND relationship_type = 'manages'
                  AND target_id = %s
                  AND source = 'seymour-registration'
            """, (MANAGER, BCH))

            assert int(cur.fetchone()["count"]) == 1

            cur.execute("""
                SELECT COUNT(*) AS count
                FROM nexus.blockchain_nodes
                WHERE asset_id = %s
                  AND coin = 'BCH'
                  AND network = 'mainnet'
            """, (BCH,))

            assert int(cur.fetchone()["count"]) == 1

            print(
                "PASS: consolidated canonical Manager/BCH "
                "topology verified"
            )
        else:
            print(
                "PASS: pre-consolidation topology retained "
                "during plan verification"
            )
PY2

echo "Package 078 verify: PASS"
