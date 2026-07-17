#!/usr/bin/env bash
set -Eeuo pipefail
PROJECT_ROOT="${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
cd "$PROJECT_ROOT"
test -f frontend/home-v2.html
test -f frontend/js/home-v2.js
for endpoint in fleet pools workers; do
  curl -fsS "http://127.0.0.1:8080/api/platform/$endpoint" | python3 -m json.tool >/dev/null
done
echo "Package 007 doctor passed."
