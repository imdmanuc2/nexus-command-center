#!/usr/bin/env bash
set -euo pipefail
REPO="${NEXUS_REPO:-$HOME/Projects/Seymour/nexus-command-center}"
cd "$REPO"
grep -q 'platform_operational_profile' backend/api/server.py && echo "PASS: operational profile routes"
grep -q 'management_model' backend/db/repositories/asset_repository.py && echo "PASS: asset operational profile persistence"
grep -q 'operationalProfileForm' frontend/cmdb-object.html && echo "PASS: CMDB operational profile editor"
grep -q 'MINING ·' frontend/js/graph.js && echo "PASS: Canvas mining hashrate label"
set -a
source backend/data/private/cmdb.env
set +a
PGPASSWORD="$NEXUS_DB_PASSWORD" psql \
  -h "$NEXUS_DB_HOST" -p "$NEXUS_DB_PORT" \
  -U "$NEXUS_DB_USER" -d "$NEXUS_DB_NAME" -Atc \
  "SELECT mission IS NOT NULL AND management_model IS NOT NULL AND lifecycle_stage IS NOT NULL FROM nexus.assets LIMIT 1" \
  | grep -q '^t$'
echo "PASS: CMDB operational profile schema"
for path in /cmdb-object.html /graph.html /api/platform/objects; do
  curl -fsS "http://localhost:8080$path" >/dev/null
  echo "PASS: $path"
done
ASSET_ID="$(curl -fsS http://localhost:8080/api/platform/objects | python3 -c 'import json,sys; d=json.load(sys.stdin); print(next((x["objectId"] for x in d.get("objects",[]) if x.get("objectType")=="asset"),""))')"
test -n "$ASSET_ID"
curl -fsS "http://localhost:8080/api/cmdb/operational-profile?assetId=$ASSET_ID" | python3 -c 'import json,sys; d=json.load(sys.stdin); assert d["status"]=="ok"; p=d["profile"]; assert "mission" in p and "managementModel" in p and "lifecycleStage" in p'
echo "PASS: operational profile API"
echo "Verify PASS"
