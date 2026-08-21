#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
cd "$ROOT"

echo "===== PACKAGE 082 VERIFY ====="

python3 - <<'PY'
import json

from backend.transports.target_resolver import resolve_target
from backend.transports.ssh_transport import SshTransport

target = resolve_target({
    "entityId": "asset-host-be24584e412bf6f6",
    "inputPayload": {
        "transport": "ssh",
    },
})

transport = SshTransport()


def run(operation):
    result = transport.execute(
        target=target,
        argv=[
            "/usr/bin/sudo",
            "-n",
            "/usr/local/libexec/seymour-blockchain-runtime",
            operation,
        ],
        timeout_seconds=30,
        secrets=[],
    )

    print()
    print(f"===== {operation.upper()} =====")
    print("exitCode =", result.exit_code)

    if result.stdout:
        print(result.stdout.rstrip())

    if result.stderr:
        print("--- stderr ---")
        print(result.stderr.rstrip())

    assert result.exit_code == 0

    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"

    return payload


info = run("info")

assert info["docker"]["version"]
assert info["docker"]["arch"] in {
    "arm64",
    "aarch64",
}

print("PASS: privileged Docker information")

inventory = run("list")

assert isinstance(inventory["containers"], list)

monero = [
    item
    for item in inventory["containers"]
    if (
        "monero" in str(item.get("name") or "").lower()
        or "monero" in str(item.get("image") or "").lower()
        or "xmr" in str(item.get("name") or "").lower()
        or "xmr" in str(item.get("image") or "").lower()
    )
]

print()
print("Monero runtime matches =", len(monero))

assert len(monero) == 0

print("PASS: trustworthy Monero runtime absence")
PY

echo
echo "===== PROHIBITED OPERATION CHECK ====="

python3 - <<'PY'
from backend.transports.target_resolver import resolve_target
from backend.transports.ssh_transport import SshTransport

target = resolve_target({
    "entityId": "asset-host-be24584e412bf6f6",
    "inputPayload": {
        "transport": "ssh",
    },
})

result = SshTransport().execute(
    target=target,
    argv=[
        "/usr/bin/sudo",
        "-n",
        "/usr/local/libexec/seymour-blockchain-runtime",
        "shell",
    ],
    timeout_seconds=20,
    secrets=[],
)

print("exitCode =", result.exit_code)
print(result.stdout.rstrip())

assert result.exit_code != 0
assert "not allow-listed" in result.stdout

print("PASS: arbitrary privileged operation rejected")
PY

echo
echo "PACKAGE 082 VERIFY PASS"
