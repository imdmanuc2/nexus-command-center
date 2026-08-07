#!/usr/bin/env bash
set -euo pipefail
P="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; R="$(cd "$P/../.." && pwd)"; cd "$R"
for f in frontend/js/nav.js frontend/home-v2.html; do [[ -f "$f.before-package-050" ]] && cp "$f.before-package-050" "$f"; done
rm -f frontend/operations-center.html frontend/js/evidence-client.js frontend/js/operations-center.js frontend/css/operations-center.css frontend/js/home-v2-evidence.js frontend/css/home-v2-evidence.css
sudo systemctl restart nexus-api.service
echo "Package 050 rollback PASS"
