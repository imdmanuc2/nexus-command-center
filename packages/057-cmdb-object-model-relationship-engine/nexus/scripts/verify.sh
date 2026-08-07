#!/usr/bin/env bash
set -euo pipefail

REPO="${NEXUS_REPO:-$HOME/Projects/Seymour/nexus-command-center}"
cd "$REPO"

for path in \
  /assets.html \
  /cmdb-object.html \
  /css/cmdb-object.css \
  /js/cmdb-object.js \
  /api/platform/objects \
  /api/platform/relationships
do
  code="$(curl -sS -o /tmp/pkg057-response -w '%{http_code}' "http://127.0.0.1:8080$path")"
  test "$code" = "200" || { echo "FAIL: $path returned HTTP $code"; cat /tmp/pkg057-response; exit 1; }
  echo "PASS: $path"
done

python3 - <<'PY'
import json
from urllib.request import urlopen

objects = json.load(urlopen("http://127.0.0.1:8080/api/platform/objects"))
assert objects["status"] == "ok"
assert isinstance(objects.get("objects"), list)
assert objects.get("count", 0) > 0
print(f"PASS: canonical objects {objects['count']}")

relationships = json.load(urlopen("http://127.0.0.1:8080/api/platform/relationships"))
assert relationships["status"] == "ok"
rows = relationships.get("relationships", [])
assert all("sourceName" in row and "targetName" in row for row in rows)
assert all("sourceHref" in row and "targetHref" in row for row in rows)
print(f"PASS: resolved relationships {len(rows)}")

candidate = next((row for row in objects["objects"] if row.get("raw")), None)
assert candidate
url = "http://127.0.0.1:8080/api/platform/objects/{}/{}".format(
    candidate["objectType"], candidate["objectId"]
)
detail = json.load(urlopen(url))
assert detail["status"] == "ok"
assert detail["object"]["displayName"]
print(f"PASS: object detail {detail['object']['displayName']}")
PY

grep -q 'cmdb-object.html' frontend/js/assets.js
grep -q 'Canonical CMDB Object' frontend/cmdb-object.html
grep -q 'cmdb_object_service' backend/modules/platform.py

echo "Verify PASS"
