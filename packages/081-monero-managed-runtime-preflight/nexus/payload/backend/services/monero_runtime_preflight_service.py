from __future__ import annotations

import time

import json
from pathlib import Path
from typing import Any

from backend.transports.target_resolver import resolve_target
from backend.transports.ssh_transport import SshTransport


HOST_ASSET_ID = "asset-host-be24584e412bf6f6"
PROVIDER_ID = "monero-mainnet"
STORAGE_PATH = "/mnt/seymour-storage/monero-mainnet"
MINIMUM_FREE_BYTES = 300 * 1024 * 1024 * 1024
P2P_PORT = 18080
RPC_PORT = 18081

CATALOG_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "config"
    / "blockchain_provider_catalog.json"
)


def _catalog_provider() -> dict[str, Any]:
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))

    providers = payload.get("providers", payload)
    if isinstance(providers, dict):
        providers = list(providers.values())

    for provider in providers:
        if str(provider.get("providerId") or "") == PROVIDER_ID:
            return provider

    raise RuntimeError("Monero provider is missing from blockchain catalog")


def _remote_target():
    return resolve_target({
        "entityId": HOST_ASSET_ID,
        "inputPayload": {
            "transport": "ssh",
        },
    })


def _run(command: list[str]) -> dict[str, Any]:
    target = _remote_target()
    transport = SshTransport()

    result = None

    for attempt in range(1, 4):
        result = transport.execute(
            target=target,
            argv=command,
            timeout_seconds=20,
            secrets=[],
        )

        # Retry only transport failures. A normal remote command
        # failure is authoritative and must not be hidden.
        if result.exit_code not in {124, 255}:
            break

        if attempt < 3:
            time.sleep(1)

    assert result is not None

    return {
        "returnCode": result.exit_code,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "timedOut": result.timed_out,
        "attempts": attempt,
    }


def _check_port(port: int) -> dict[str, Any]:
    result = _run([
        "sh",
        "-lc",
        (
            "if ss -ltnH | awk '{print $4}' "
            f"| grep -Eq '(^|:){port}$'; "
            "then echo IN_USE; else echo AVAILABLE; fi"
        ),
    ])

    available = (
        result["returnCode"] == 0
        and result["stdout"].strip() == "AVAILABLE"
    )

    return {
        "port": port,
        "available": available,
        "evidence": result["stdout"].strip(),
    }


def _privileged_helper(operation: str) -> dict[str, Any]:
    result = _run([
        "/usr/bin/sudo",
        "-n",
        "/usr/local/libexec/seymour-blockchain-runtime",
        operation,
    ])

    payload = None

    if result["returnCode"] == 0:
        try:
            payload = json.loads(result["stdout"])
        except json.JSONDecodeError:
            payload = None

    return {
        "returnCode": result["returnCode"],
        "stdout": result["stdout"],
        "stderr": result["stderr"],
        "payload": payload,
    }


def preflight() -> dict[str, Any]:
    provider = _catalog_provider()
    target = _remote_target()

    architecture = _run(["uname", "-m"])

    docker_path = _run([
        "sh",
        "-lc",
        "command -v docker || true",
    ])

    docker_socket = _run([
        "sh",
        "-lc",
        (
            "if test -S /var/run/docker.sock || test -S /run/docker.sock; "
            "then echo PRESENT; else echo MISSING; fi"
        ),
    ])

    storage = _run([
        "sh",
        "-lc",
        (
            f"test -d {STORAGE_PATH!s} && "
            f"test -w {STORAGE_PATH!s} && "
            f"df -B1 --output=avail {STORAGE_PATH!s} | tail -1"
        ),
    ])

    helper_info = _privileged_helper("info")
    helper_list = _privileged_helper("list")

    privileged_execution_available = bool(
        helper_info["returnCode"] == 0
        and isinstance(helper_info["payload"], dict)
        and helper_info["payload"].get("status") == "ok"
    )

    docker_inventory_available = bool(
        helper_list["returnCode"] == 0
        and isinstance(helper_list["payload"], dict)
        and helper_list["payload"].get("status") == "ok"
        and isinstance(
            helper_list["payload"].get("containers"),
            list,
        )
    )

    runtime_matches: list[str] = []

    if docker_inventory_available:
        for item in helper_list["payload"]["containers"]:
            name = str(item.get("name") or "").lower()
            image = str(item.get("image") or "").lower()

            if (
                "monero" in name
                or "monero" in image
                or "xmr" in name
                or "xmr" in image
            ):
                runtime_matches.append(
                    str(
                        item.get("name")
                        or item.get("id")
                        or item.get("image")
                        or ""
                    )
                )

    free_bytes = None

    if storage["returnCode"] == 0:
        try:
            free_bytes = int(storage["stdout"].strip())
        except ValueError:
            free_bytes = None

    architecture_name = architecture["stdout"].strip().lower()

    architecture_supported = architecture_name in {
        "aarch64",
        "arm64",
        "x86_64",
        "amd64",
    }

    docker_installed = bool(
        docker_path["stdout"].strip()
    )

    docker_socket_present = (
        docker_socket["stdout"].strip() == "PRESENT"
    )

    p2p = _check_port(P2P_PORT)
    rpc = _check_port(RPC_PORT)

    runtime_absent = (
        docker_inventory_available
        and len(runtime_matches) == 0
    )

    checks = {
        "hostResolved": bool(target.host),
        "sshReachable": architecture["returnCode"] == 0,
        "architectureSupported": architecture_supported,

        "dockerInstalled": docker_installed,
        "dockerSocketPresent": docker_socket_present,

        # Canonical Docker access is through the Package 082
        # allow-listed privileged helper. Direct Docker socket access
        # by the managed SSH account is intentionally unnecessary.
        "dockerDaemonAccessible": (
            privileged_execution_available
        ),
        "privilegedExecutionAvailable": (
            privileged_execution_available
        ),

        "storagePresent": storage["returnCode"] == 0,
        "storageWritable": storage["returnCode"] == 0,
        "capacitySufficient": (
            free_bytes is not None
            and free_bytes >= MINIMUM_FREE_BYTES
        ),

        "p2pPortAvailable": p2p["available"],
        "rpcPortAvailable": rpc["available"],

        "runtimeInventoryAvailable": (
            docker_inventory_available
        ),
        "runtimeAbsent": runtime_absent,
    }

    ready = all(checks.values())

    blockers = [
        key
        for key, value in checks.items()
        if not value
    ]

    return {
        "status": "ready" if ready else "blocked",
        "providerId": PROVIDER_ID,
        "provider": {
            "coin": provider.get("coin"),
            "name": provider.get("name"),
            "network": provider.get("network"),
        },
        "host": {
            "assetId": HOST_ASSET_ID,
            "address": target.host,
            "architecture": architecture_name,
        },
        "storage": {
            "path": STORAGE_PATH,
            "freeBytes": free_bytes,
            "minimumFreeBytes": MINIMUM_FREE_BYTES,
        },
        "docker": {
            "installed": docker_installed,
            "socketPresent": docker_socket_present,
            "daemonAccessible": (
                privileged_execution_available
            ),
            "privilegedExecutionAvailable": (
                privileged_execution_available
            ),
            "accessMethod": (
                "seymour-blockchain-runtime-helper"
                if privileged_execution_available
                else None
            ),
        },
        "ports": {
            "p2p": p2p,
            "rpc": rpc,
        },
        "runtimeInventoryAvailable": (
            docker_inventory_available
        ),
        "runtimeMatches": runtime_matches,
        "checks": checks,
        "blockers": blockers,
        "ready": ready,
    }
