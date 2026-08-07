#!/usr/bin/env bash
set -euo pipefail

PKG_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(cd "$PKG_DIR/../.." && pwd)"

"$PKG_DIR/scripts/doctor.sh"

sudo systemctl daemon-reload
sudo systemctl restart nexus-api.service
sudo systemctl restart nexus-change-rollback-worker.service

sleep 3

sudo systemctl is-active --quiet nexus-api.service
sudo systemctl is-active --quiet nexus-change-rollback-worker.service

echo "Package 047 R4 corrective overlay installed"
