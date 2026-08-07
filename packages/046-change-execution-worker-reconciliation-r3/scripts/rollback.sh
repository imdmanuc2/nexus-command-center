#!/usr/bin/env bash
set -euo pipefail
sudo systemctl disable --now nexus-change-execution-worker.service 2>/dev/null || true
sudo rm -f /etc/systemd/system/nexus-change-execution-worker.service
sudo systemctl daemon-reload
echo "Worker service removed. Database history was intentionally preserved."
