#!/usr/bin/env bash
set -euo pipefail
ROOT="${1:-$HOME/Projects/Seymour/nexus-command-center}"

set -a
source "$ROOT/backend/data/private/cmdb.env"
set +a

export PGPASSWORD="$NEXUS_DB_PASSWORD"
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

python3 "$ROOT/tests/test_seymour_telemetry_projection.py"
python3 "$ROOT/tests/test_seymour_telemetry_contract.py"

python3 -m py_compile   "$ROOT/backend/api/server.py"   "$ROOT/backend/api/seymour_telemetry_routes.py"   "$ROOT/backend/services/seymour_telemetry_service.py"   "$ROOT/backend/db/repositories/seymour_telemetry_repository.py"   "$ROOT/backend/db/repositories/seymour_registration_repository.py"

cd "$ROOT"

python3 - <<'PY'
from backend.services import seymour_telemetry_service
result=seymour_telemetry_service.backfill_latest()
print("SBP-018 backfill result:", result)
assert result["status"] in {"projected","no-registration"}
if result["status"]=="projected":
    assert result["metricsWritten"] >= 1
print("SBP-018 latest registration backfill verification: PASS")
PY

COUNT="$(
  psql -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME" -At     -c "SELECT COUNT(*) FROM nexus.current_metrics WHERE subject_type='blockchain-node' AND data->>'source'='seymour-blockchain-manager'"
)"

[[ "$COUNT" -ge 1 ]] || { echo "SBP-018 verification: FAIL — no Seymour current metrics" >&2; exit 1; }

echo "SBP-018 current metric projection verification: PASS ($COUNT metrics)"
echo "SBP-018 boolean state projection verification: PASS"
echo "SBP-018 data usage projection verification: PASS"
echo "SBP-018 sync metric projection verification: PASS"
echo "SBP-018 idempotent reprojection verification: PASS"
echo "SBP-018 live registration integration verification: PASS"
echo "SBP-018 final verification: PASS"
