#!/usr/bin/env bash
set -euo pipefail
echo "Rollback uses the timestamped backup printed by install.sh. Restore backend/api/server.py and frontend/js/assets.js, remove Package 039 modules, then restart nexus-api.service. Database tables are retained for audit safety."
