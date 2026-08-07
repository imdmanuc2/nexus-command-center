#!/usr/bin/env bash
set -euo pipefail
DASH=/home/imdmanuc/bitcoin-dashboard
STAMP=$(date +%Y%m%d-%H%M%S)
cp "$DASH/server.js" "$DASH/server.js.before-ckpool-telemetry-$STAMP"
cp "$(dirname "$0")/../payload/server.js" "$DASH/server.js"
sudo systemctl restart miner-dashboard.service
sleep 2
systemctl is-active --quiet miner-dashboard.service
echo 'Install PASS'
