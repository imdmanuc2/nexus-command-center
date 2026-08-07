#!/usr/bin/env bash
set -euo pipefail
P="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; R="$(cd "$P/../.." && pwd)"; cd "$R"
install -D -m0644 "$P/frontend/operations-center.html" frontend/operations-center.html
install -D -m0644 "$P/frontend/js/evidence-client.js" frontend/js/evidence-client.js
install -D -m0644 "$P/frontend/js/operations-center.js" frontend/js/operations-center.js
install -D -m0644 "$P/frontend/css/operations-center.css" frontend/css/operations-center.css
install -D -m0644 "$P/frontend/js/home-v2-evidence.js" frontend/js/home-v2-evidence.js
install -D -m0644 "$P/frontend/css/home-v2-evidence.css" frontend/css/home-v2-evidence.css
/usr/bin/python3 "$P/scripts/patch_frontend.py"
sudo systemctl restart nexus-api.service; sleep 2
echo "Package 050 install PASS"
