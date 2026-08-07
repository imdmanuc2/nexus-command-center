#!/usr/bin/env bash
set -euo pipefail
cd ~/Projects/Seymour/nexus-command-center
python3 -m backend.jobs.platform_sync_job >/tmp/nexus-package-054-sync.json
python3 - <<'PY'
from backend.db.repositories.worker_repository import list_active_workers
workers=list_active_workers()
btc=[w for w in workers if str(w.get('coin') or '').upper()=='BTC']
assert btc, 'No active BTC worker after synchronization'
for w in btc:
    assert float(w.get('currentHashrate') or 0) > 0
    assert w.get('lastShareAt') or w.get('last_share_at')
    print('PASS: active BTC worker', w.get('displayName') or w.get('display_name'), w.get('currentHashrate') or w.get('current_hashrate'))
print('PASS: CKPool telemetry consumed by Nexus')
PY
echo 'Verify PASS'
