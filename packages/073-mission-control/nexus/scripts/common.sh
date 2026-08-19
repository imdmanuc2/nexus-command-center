#!/usr/bin/env bash
set -euo pipefail

PACKAGE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$PACKAGE_ROOT/../../.." && pwd)"
PAYLOAD_ROOT="$PACKAGE_ROOT/payload"
BACKUP_MARKER="$REPO_ROOT/.package-073-last-backup"

pass() { printf 'PASS: %s\n' "$1"; }
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }
warn() { printf 'WARN: %s\n' "$1"; }
