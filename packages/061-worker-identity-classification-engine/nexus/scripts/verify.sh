#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
cd "$ROOT"
set -a; source backend/data/private/cmdb.env; set +a
/usr/bin/python3 -m backend.jobs.platform_sync_job >/tmp/package-061-sync.log
python3 - <<'PY'
import json, urllib.request, time
for _ in range(10):
    with urllib.request.urlopen('http://localhost:8080/api/platform/workers', timeout=10) as r: data=json.load(r)
    rows=[w for w in data.get('workers',[]) if w.get('sourceSystem')=='seymour-native-stratum']
    cpu=[w for w in rows if str(w.get('workerName','')).endswith('.cpu01')]
    if cpu and cpu[0].get('assetId')=='asset-bab403ab': break
    time.sleep(2)
else: raise AssertionError('cpu01 did not reconcile to asset-bab403ab')
w=cpu[0]
assert w.get('workerType')=='cpu', w
assert w.get('hardwareType')=='Virtual CPU', w
assert w.get('currentSession') is True, w
assert float(w.get('currentHashrate') or 0)>0, w
assert w.get('poolInstanceId')=='seymour-btc-solo', w
print('PASS: cpu01 matched to CPU Mining VM')
print('PASS: CPU worker classification')
print('PASS: live CPU hashrate')
print('PASS: current Seymour pool assignment')
PY
curl -fsS http://localhost:8080/api/platform/topology >/dev/null
echo "PASS: /api/platform/topology"
grep -q 'CPU MINER' frontend/js/graph.js
grep -q 'formatHashrate' frontend/js/graph.js
echo "PASS: Canvas CPU miner hashrate rendering"
echo "Verify PASS"
