#!/usr/bin/env bash
set -euo pipefail
ROOT="$HOME/Projects/Seymour/nexus-command-center"
cd "$ROOT"
python3 -m backend.jobs.platform_sync_job >/tmp/package-060-sync.json
python3 - <<'PY'
import json, urllib.request

def get(path):
    with urllib.request.urlopen('http://localhost:8080'+path, timeout=10) as r:
        return json.load(r)
workers=get('/api/platform/workers')
topology=get('/api/platform/topology')
pools=get('/api/platform/pools')
seymour=[w for w in workers.get('workers',[]) if w.get('sourceSystem')=='seymour-native-stratum' and w.get('currentSession') and w.get('activityState')=='active']
assert len(seymour)==2, f'expected 2 current Seymour workers, got {len(seymour)}'
assert all(w.get('assetId') for w in seymour), 'Seymour workers must be bound to CMDB assets'
asset_ids={w['assetId'] for w in seymour}
assert len(asset_ids)==2, f'expected 2 distinct physical assets, got {len(asset_ids)}'
assert all(float(w.get('currentHashrate') or 0)>0 for w in seymour), 'live Seymour workers must have hashrate'
active_edges=[e for e in topology.get('edges',[]) if e.get('type')=='mines-on' and e.get('status','active')=='active' and e.get('source') in asset_ids]
assert len(active_edges)==2, f'expected 2 active ASIC pool paths, got {len(active_edges)}'
assert {e.get('target') for e in active_edges}=={'seymour-btc-solo'}, active_edges
sp=next(p for p in pools.get('pools',[]) if p.get('poolId')=='seymour-btc-solo')
assert float(sp.get('currentHashrate') or 0)>0, 'Seymour pool must expose live hashrate'
print('PASS: 2 current Seymour workers')
print('PASS: 2 distinct CMDB ASIC assets')
print('PASS: one active Seymour path per ASIC')
print('PASS: live miner hashrates')
print('PASS: Seymour pool live hashrate')
PY
for path in /graph.html /api/platform/workers /api/platform/topology /api/platform/pools; do
  curl -fsS "http://localhost:8080$path" >/dev/null
  echo "PASS: $path"
done
grep -q 'MINING ·' frontend/js/graph.js
echo 'PASS: Canvas mining hashrate label'
echo 'Verify PASS'
