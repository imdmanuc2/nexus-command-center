#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"

PKG="packages/082-managed-blockchain-privileged-runtime-helper"

TARGET_HOST="192.168.1.154"
TARGET_USER="umbrel"
IDENTITY="$HOME/.ssh/nexus_managed_hosts"
KNOWN_HOSTS="$ROOT/backend/data/private/known_hosts"

REMOTE_STAGE="/home/umbrel/.seymour-package-082"

echo "===== PACKAGE 082 INSTALL ====="
echo
echo "This package requires ONE interactive sudo authorization on .154"
echo "to install the privileged helper and sudoers policy."
echo

ssh_opts=(
  -i "$IDENTITY"
  -o IdentitiesOnly=yes
  -o StrictHostKeyChecking=yes
  -o UserKnownHostsFile="$KNOWN_HOSTS"
)

echo "===== CREATE REMOTE STAGING ====="

ssh "${ssh_opts[@]}" \
  "$TARGET_USER@$TARGET_HOST" \
  "rm -rf '$REMOTE_STAGE' && mkdir -p '$REMOTE_STAGE'"

scp "${ssh_opts[@]}" \
  "$PKG/payload/seymour-blockchain-runtime" \
  "$TARGET_USER@$TARGET_HOST:$REMOTE_STAGE/seymour-blockchain-runtime"

scp "${ssh_opts[@]}" \
  "$PKG/payload/nexus-seymour-blockchain-runtime" \
  "$TARGET_USER@$TARGET_HOST:$REMOTE_STAGE/nexus-seymour-blockchain-runtime"

echo
echo "===== INSTALL PRIVILEGED HELPER ====="
echo "Enter the .154 umbrel sudo password when prompted."

ssh -t "${ssh_opts[@]}" \
  "$TARGET_USER@$TARGET_HOST" \
  "
    set -e

    sudo install \
      -o root \
      -g root \
      -m 0755 \
      '$REMOTE_STAGE/seymour-blockchain-runtime' \
      /usr/local/libexec/seymour-blockchain-runtime

    sudo install \
      -o root \
      -g root \
      -m 0440 \
      '$REMOTE_STAGE/nexus-seymour-blockchain-runtime' \
      /etc/sudoers.d/nexus-seymour-blockchain-runtime

    sudo visudo \
      -cf \
      /etc/sudoers.d/nexus-seymour-blockchain-runtime

    rm -rf '$REMOTE_STAGE'
  "

echo
echo "PASS: privileged runtime helper installed"

echo
echo "===== NON-INTERACTIVE PRIVILEGE TEST ====="

ssh "${ssh_opts[@]}" \
  "$TARGET_USER@$TARGET_HOST" \
  "sudo -n /usr/local/libexec/seymour-blockchain-runtime info"

echo
echo "PASS: approved helper works without interactive sudo"

echo "PACKAGE 082 INSTALL PASS"
