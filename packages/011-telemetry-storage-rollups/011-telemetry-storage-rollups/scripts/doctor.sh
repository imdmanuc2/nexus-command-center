#!/usr/bin/env bash
set -Eeuo pipefail
cd "${PROJECT_ROOT:-$HOME/Projects/Seymour/nexus-command-center}"
test -f backend/data/private/cmdb.env
for e in fleet workers pools; do curl -fsS "http://127.0.0.1:8080/api/platform/$e"|python3 -m json.tool >/dev/null; done
echo "Package 011 doctor passed."
