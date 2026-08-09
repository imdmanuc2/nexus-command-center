#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/home/imdmanuc/Projects/Seymour/nexus-command-center}"

cd "$ROOT"

set -a
source backend/data/private/cmdb.env
set +a

python3 \
  scripts/acceptance/verify_sbp028_live_runtime_state.py
