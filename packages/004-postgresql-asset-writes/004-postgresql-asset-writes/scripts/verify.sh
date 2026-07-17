#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
cd "$PROJECT_ROOT"

ASSET_IP="${ASSET_IP:-192.168.1.154}"
BEFORE_MTIME="$(stat -c %Y backend/data/assets.json 2>/dev/null || echo missing)"
OLD_NOTE="$(curl -fsS http://127.0.0.1:8080/api/cmdb/assets | jq -r --arg ip "$ASSET_IP" '.assets[] | select(.ip==$ip) | .notes' | head -1)"
TEST_NOTE="PostgreSQL write verification $(date -u +%Y-%m-%dT%H:%M:%SZ)"

curl -fsS -X POST -H 'Content-Type: application/json' \
  http://127.0.0.1:8080/api/assets/update \
  -d "$(jq -n --arg ip "$ASSET_IP" --arg note "$TEST_NOTE" '{ip:$ip,updates:{notes:$note,_actorType:"system",_actorId:"package-004-verify",_source:"postgresql-write-verification",_reason:"Verify PostgreSQL CMDB write cutover"}}')" \
  | jq

READ_NOTE="$(curl -fsS http://127.0.0.1:8080/api/cmdb/assets | jq -r --arg ip "$ASSET_IP" '.assets[] | select(.ip==$ip) | .notes' | head -1)"
[[ "$READ_NOTE" == "$TEST_NOTE" ]] || { echo "ERROR: PostgreSQL read did not return test note"; exit 1; }

AFTER_MTIME="$(stat -c %Y backend/data/assets.json 2>/dev/null || echo missing)"
[[ "$BEFORE_MTIME" == "$AFTER_MTIME" ]] || { echo "ERROR: assets.json changed during PostgreSQL write"; exit 1; }

curl -fsS -X POST -H 'Content-Type: application/json' \
  http://127.0.0.1:8080/api/assets/update \
  -d "$(jq -n --arg ip "$ASSET_IP" --arg note "$OLD_NOTE" '{ip:$ip,updates:{notes:$note,_actorType:"system",_actorId:"package-004-verify",_source:"postgresql-write-verification",_reason:"Restore note after PostgreSQL verification"}}')" \
  >/dev/null

echo "PostgreSQL asset write verified."
echo "assets.json remained unchanged."
curl -fsS 'http://127.0.0.1:8080/api/cmdb/audit?limit=5' | jq '{source,count,events:[.events[]|{action,assetId,source,reason}]}'
