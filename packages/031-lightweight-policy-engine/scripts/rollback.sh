#!/usr/bin/env bash
set -euo pipefail
PKG="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$PKG/../.." && pwd)"
cd "$ROOT"
echo "Package 031 rollback is intentionally conservative."
echo "Database decision history is retained. Restore source files from Git if rollback is required."
