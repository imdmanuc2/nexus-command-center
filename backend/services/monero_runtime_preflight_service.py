from __future__ import annotations

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

    result = transport.execute(
        target=target,
        argv=command,
        timeout_seconds=20,
        secrets=[],
    )

    return {
        "returnCode": result.exit_code,
        "stdout": result.stdout,
        "stderr": result.stderr,
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

    docker_access = _run([
        "sh",
        "-lc",
        (
            "docker version --format '{{.Server.Version}}' "
            "2>/dev/null || true"
        ),
    ])

    sudo_access = _run([
        "sh",
        "-lc",
        (
            "if sudo -n true >/dev/null 2>&1; "
            "then echo AVAILABLE; else echo UNAVAILABLE; fi"
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

    docker_inventory_available = bool(
        docker_access["returnCode"] == 0
        and docker_access["stdout"].strip()
    )

    runtime_matches: list[str] = []

    if docker_inventory_available:
        runtime = _run([
            "sh",
            "-lc",
            (
                "docker ps -a --format '{{.Names}}' "
                "| grep -Ei 'monero|xmr' || true"
            ),
        ])

        runtime_matches = [
            line.strip()
            for line in runtime["stdout"].splitlines()
            if line.strip()
        ]

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

    privileged_execution_available = (
        sudo_access["stdout"].strip() == "AVAILABLE"
    )

    p2p = _check_port(P2P_PORT)
    rpc = _check_port(RPC_PORT)

    checks = {
        "hostResolved": bool(target.host),
        "sshReachable": architecture["returnCode"] == 0,
        "architectureSupported": architecture_supported,

        # Docker is separated into installation, daemon access,
        # and privilege state. Docker daemon access is intentionally
        # NOT granted to the managed SSH user merely to satisfy preflight.
        "dockerInstalled": docker_installed,
        "dockerSocketPresent": docker_socket_present,
        "dockerDaemonAccessible": docker_inventory_available,
        "privilegedExecutionAvailable": privileged_execution_available,

        "storagePresent": storage["returnCode"] == 0,
        "storageWritable": storage["returnCode"] == 0,
        "capacitySufficient": (
            free_bytes is not None
            and free_bytes >= MINIMUM_FREE_BYTES
        ),

        "p2pPortAvailable": p2p["available"],
        "rpcPortAvailable": rpc["available"],

        # Runtime absence can only be trusted when the Docker inventory
        # was actually readable.
        "runtimeInventoryAvailable": docker_inventory_available,
        "runtimeAbsent": (
            docker_inventory_available
            and len(runtime_matches) == 0
        ),
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
            "daemonAccessible": docker_inventory_available,
            "privilegedExecutionAvailable": (
                privileged_execution_available
            ),
        },
        "ports": {
            "p2p": p2p,
            "rpc": rpc,
        },
        "runtimeInventoryAvailable": docker_inventory_available,
        "runtimeMatches": runtime_matches,
        "checks": checks,
        "blockers": blockers,
        "ready": ready,
    }
