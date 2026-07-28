#!/usr/bin/env bash
set -euo pipefail
REPO="$HOME/Projects/Seymour/nexus-command-center"
cd "$REPO"
python3 -m backend.jobs.platform_sync_job >/tmp/pkg055-platform-sync.json
python3 - <<'PY'
import json
from urllib.request import urlopen
with urlopen('http://localhost:8080/api/platform/workers', timeout=10) as r:
    payload=json.load(r)
workers=payload.get('workers', [])
btc=next((w for w in workers if w.get('sourceWorkerId')=='bc1qasa0lk6l7s47sw9wusqdpug4scryckjjgacepv'), None)
cpu=next((w for w in workers if w.get('sourceWorkerId')=='bc1q8ucazpveqtml7kq0k08z20zm3hzyqae0d2tvjf'), None)
assert btc, 'BTC Nano 3s worker missing'
assert btc.get('status') == 'online', btc
assert btc.get('activityState') == 'active', btc
assert btc.get('connectionConfirmed') is True, btc
assert float(btc.get('currentHashrate') or 0) > 0, btc
assert btc.get('observedState', {}).get('evidence') == 'live-activity-confirmed', btc
assert cpu, 'CPU worker missing'
assert cpu.get('status') != 'online', cpu
assert float(cpu.get('currentHashrate') or 0) == 0, cpu
print(f"PASS: BTC Nano 3s online at {btc['currentHashrate']} H/s")
print("PASS: inactive CPU worker not online")
PY
echo "Verify PASS"
