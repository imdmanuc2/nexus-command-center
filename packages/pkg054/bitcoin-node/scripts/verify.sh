#!/usr/bin/env bash
set -euo pipefail
JSON=$(curl -fsS http://127.0.0.1:3000/api/ckpool/status)
python3 - <<'PY' "$JSON"
import json,sys
p=json.loads(sys.argv[1])
assert p['status']=='ok'
assert isinstance(p['workers'], list)
active=[w for w in p['workers'] if w.get('online')]
assert active, 'No active CKPool workers detected'
assert active[0]['currentHashrate'] > 0
assert active[0]['lastShareAt']
print('PASS: CKPool telemetry endpoint')
print('PASS: active workers:', len(active))
for w in active:
    print(f"PASS: {w['sourceWorkerId']} {w['currentHashrate']} H/s")
PY
echo 'Verify PASS'
