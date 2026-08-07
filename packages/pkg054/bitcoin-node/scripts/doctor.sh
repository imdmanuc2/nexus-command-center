#!/usr/bin/env bash
set -euo pipefail
DASH=/home/imdmanuc/bitcoin-dashboard
LOGDIR=/home/imdmanuc/Downloads/ckolivas-ckpool-bb7b0aebe08e/logs
[[ -f "$DASH/server.js" ]] && echo 'PASS: dashboard server.js' || { echo 'FAIL: dashboard server.js'; exit 1; }
[[ -f "$LOGDIR/pool/pool.status" ]] && echo 'PASS: CKPool pool.status' || { echo 'FAIL: CKPool pool.status'; exit 1; }
[[ -d "$LOGDIR/users" ]] && echo 'PASS: CKPool users directory' || { echo 'FAIL: CKPool users directory'; exit 1; }
systemctl is-active --quiet miner-dashboard.service && echo 'PASS: miner-dashboard.service active' || { echo 'FAIL: miner-dashboard.service inactive'; exit 1; }
echo 'Doctor PASS'
