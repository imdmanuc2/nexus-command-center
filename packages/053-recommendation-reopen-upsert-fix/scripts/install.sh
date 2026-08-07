#!/usr/bin/env bash
set -euo pipefail
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(cd "$PKG/../.." && pwd)"
TARGET="$ROOT/backend/db/repositories/recommendation_repository.py"
STAMP="$(date +%Y%m%d-%H%M%S)"
cp "$TARGET" "$TARGET.before-recommendation-upsert-$STAMP"
cp "$PKG/payload/backend/db/repositories/recommendation_repository.py" "$TARGET"
python3 -m py_compile "$TARGET"
sudo systemctl restart nexus-api.service
sudo systemctl is-active --quiet nexus-api.service
echo "Install PASS"
