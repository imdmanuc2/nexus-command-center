#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"

set -a
source backend/data/private/cmdb.env
set +a
export PGPASSWORD="$NEXUS_DB_PASSWORD"
PSQL=(psql -q -At -v ON_ERROR_STOP=1 -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME")

for table in verification_profiles verification_profile_steps verification_runs \
  verification_step_runs verification_evidence verification_events; do
  "${PSQL[@]}" -c "SELECT to_regclass('nexus.$table') IS NOT NULL;" | grep -qx t
done
echo "verification schema PASS"

/usr/bin/python3 -m py_compile \
  backend/db/repositories/verification_repository.py \
  backend/services/verification_service.py \
  backend/jobs/verification_worker.py \
  backend/modules/platform_verifications.py \
  backend/api/patch_verification_routes.py \
  backend/api/server.py
echo "Python compilation PASS"

! grep -q "backend.transports.transport_factory" backend/services/verification_service.py
echo "verification execution adapter PASS"

grep -q "from backend.modules import platform_verifications" backend/api/server.py
grep -q "PACKAGE-048-VERIFICATION-GET-BEGIN" backend/api/server.py
grep -q "PACKAGE-048-VERIFICATION-POST-BEGIN" backend/api/server.py
echo "HTTP route registration PASS"

sudo systemctl is-active --quiet nexus-verification-worker.service
sudo systemctl is-active --quiet nexus-api.service
echo "verification services PASS"

for _ in $(seq 1 20); do
  curl -fsS http://127.0.0.1:8080/api/verifications/profiles >/dev/null 2>&1 && break
  sleep 1
done

curl -fsS http://127.0.0.1:8080/api/verifications/profiles | \
  /usr/bin/python3 -c "import json,sys; data=json.load(sys.stdin); assert data['status']=='ok'; assert isinstance(data['profiles'],list)"
curl -fsS "http://127.0.0.1:8080/api/verifications/runs?limit=1" | \
  /usr/bin/python3 -c "import json,sys; data=json.load(sys.stdin); assert data['status']=='ok'; assert isinstance(data['runs'],list)"
echo "verification APIs PASS"

RUN_ID="$(curl -fsS -X POST http://127.0.0.1:8080/api/verifications/run \
  -H 'Content-Type: application/json' -d '{
    "profileKey":"nexus.local.identity",
    "targetType":"asset",
    "targetId":"nexus-local",
    "assetId":"nexus-local",
    "transport":"local",
    "parameters":{},
    "requestedBy":"package-048-verification"
  }' | /usr/bin/python3 -c "import json,sys; print(json.load(sys.stdin)['run_id'])")"

cleanup() {
  "${PSQL[@]}" -c "DELETE FROM nexus.verification_runs WHERE run_id='$RUN_ID'::uuid;" >/dev/null || true
}
trap cleanup EXIT

for _ in $(seq 1 40); do
  STATUS="$("${PSQL[@]}" -c "SELECT status FROM nexus.verification_runs WHERE run_id='$RUN_ID'::uuid;")"
  [[ "$STATUS" == "passed" ]] && break
  if [[ "$STATUS" == "failed" ]]; then
    curl -fsS "http://127.0.0.1:8080/api/verifications/runs/$RUN_ID" || true
    exit 1
  fi
  sleep 1
done

"${PSQL[@]}" -c "SELECT status='passed' AND result='passed' AND score=100 AND completed_at IS NOT NULL FROM nexus.verification_runs WHERE run_id='$RUN_ID'::uuid;" | grep -qx t
"${PSQL[@]}" -c "SELECT COUNT(*)=1 FROM nexus.verification_step_runs WHERE run_id='$RUN_ID'::uuid AND status='passed';" | grep -qx t
"${PSQL[@]}" -c "SELECT COUNT(*)>=1 FROM nexus.verification_evidence WHERE run_id='$RUN_ID'::uuid;" | grep -qx t
"${PSQL[@]}" -c "SELECT COUNT(*)>=2 FROM nexus.verification_events WHERE run_id='$RUN_ID'::uuid;" | grep -qx t

curl -fsS "http://127.0.0.1:8080/api/verifications/runs/$RUN_ID" | \
  /usr/bin/python3 -c "import json,sys; data=json.load(sys.stdin); assert data['status']=='ok'; assert data['run']['status']=='passed'"

echo "verification lifecycle PASS"
echo "Package 048 verification PASS"
