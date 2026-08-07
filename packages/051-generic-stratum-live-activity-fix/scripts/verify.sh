#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$ROOT"
python3 -m py_compile backend/services/generic_stratum_sync_service.py
python3 - <<'PY'
from pathlib import Path
p=Path('backend/services/generic_stratum_sync_service.py')
s=p.read_text()
checks={
 'relationship active parameter': 'active: bool = True',
 'inactive relationship status': '"active" if active else "inactive"',
 'no cumulative share activity': 'acceptedShares is cumulative historical data',
 'live relationship gating': 'active=worker_online',
 'telemetry propagation': '"telemetryAvailable": telemetry_available',
}
for name, needle in checks.items():
    if needle not in s:
        raise SystemExit(f'FAIL: {name}')
    print(f'PASS: {name}')
PY
sudo systemctl is-active --quiet nexus-api.service
echo "PASS: nexus-api.service active"
# Run one full sync so worker sessions and topology relationships are reconciled.
/usr/bin/python3 -m backend.jobs.platform_sync_job >/tmp/nexus-package-051-sync.json
python3 - <<'PY'
import json
p=json.load(open('/tmp/nexus-package-051-sync.json'))
assert p.get('status') == 'ok', p
print('PASS: platform sync')
print(json.dumps({
 'workerActivityReconciliation': p.get('workerActivityReconciliation'),
 'topologyReconciliation': p.get('topologyReconciliation'),
}, indent=2))
PY
echo "Verify PASS"
