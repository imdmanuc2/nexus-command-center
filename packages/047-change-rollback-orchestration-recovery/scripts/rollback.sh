#!/usr/bin/env bash
set -euo pipefail
sudo systemctl disable --now nexus-change-rollback-worker.service 2>/dev/null || true
sudo rm -f /etc/systemd/system/nexus-change-rollback-worker.service
sudo systemctl daemon-reload
echo 'Package 047 worker disabled. Database records preserved.'
