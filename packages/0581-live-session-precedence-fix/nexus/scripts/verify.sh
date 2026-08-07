#!/usr/bin/env bash
set -euo pipefail
REPO="$HOME/Projects/Seymour/nexus-command-center"
cd "$REPO"
python3 -m backend.jobs.platform_sync_job >/tmp/nexus-0581-sync.json
python3 - <<'PY'
from backend.db.repositories.worker_repository import list_active_workers
from backend.db.repositories.relationship_repository import list_active_relationships

workers = list_active_workers()
seymour = [w for w in workers if w.get('sourceSystem') == 'seymour-native-stratum']
assert len(seymour) == 2, f'expected 2 active Seymour workers, got {len(seymour)}'
assert all(w.get('assetId') for w in seymour), 'Seymour workers must match CMDB assets'
assert {w.get('assetId') for w in seymour} == {'asset-28a5a306', 'asset-b63808dd'}
assert not any(w.get('displayName') == 'CPU Mining VM' for w in workers), 'inactive CPU worker still active'

rels = list_active_relationships()
active_mines = [r for r in rels if r.get('relationshipType') == 'mines-on' and r.get('sourceType') == 'asset']
for asset_id in ('asset-28a5a306', 'asset-b63808dd'):
    targets = {r.get('targetId') for r in active_mines if r.get('sourceId') == asset_id}
    assert targets == {'seymour-btc-solo'}, f'{asset_id} active targets: {targets}'
print('PASS: Seymour workers matched to CMDB assets')
print('PASS: one active pool relationship per ASIC')
print('PASS: stale BCH and CKPool paths retired')
print('PASS: inactive CPU worker excluded')
PY
python3 - <<'PY'
import json, urllib.request
with urllib.request.urlopen('http://localhost:8080/api/platform/topology', timeout=5) as r:
    data=json.load(r)
nodes={n['id']:n for n in data.get('nodes',[])}
assert 'seymour-btc-solo' in nodes
assert float((nodes['seymour-btc-solo'].get('properties') or {}).get('currentHashrate') or 0) > 0
ck=nodes.get('pool-192-168-1-169-3333-btc')
if ck:
    assert float((ck.get('properties') or {}).get('currentHashrate') or 0) == 0
print('PASS: Seymour pool owns live hashrate')
print('PASS: CKPool does not inherit Seymour hashrate')
PY
curl -fsS http://localhost:8080/graph.html >/dev/null
echo "PASS: /graph.html"
echo "Verify PASS"
