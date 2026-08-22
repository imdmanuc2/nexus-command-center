from __future__ import annotations

import time

import json
from typing import Any

from backend.services.monero_runtime_preflight_service import preflight
from backend.transports.ssh_transport import SshTransport
from backend.transports.target_resolver import resolve_target


HOST_ASSET_ID = "asset-host-be24584e412bf6f6"
PROVIDER_ID = "monero-mainnet"
APP_ID = "seymour-monero-node"

EXECUTION_CONFIRMATION = "INSTALL-SEYMOUR-MONERO"
NATIVE_CONFIRMATION = "INSTALL-seymour-monero-node"

APP_STORE_ROOT = "/home/umbrel/umbrel/app-stores"


def _target():
    return resolve_target({
        "entityId": HOST_ASSET_ID,
        "inputPayload": {
            "transport": "ssh",
        },
    })


def _run(argv: list[str], timeout_seconds: int = 30):
    return SshTransport().execute(
        target=_target(),
        argv=argv,
        timeout_seconds=timeout_seconds,
        secrets=[],
    )


def _run_readonly(
    argv: list[str],
    timeout_seconds: int = 30,
):
    result = None

    for attempt in range(1, 4):
        result = _run(
            argv,
            timeout_seconds=timeout_seconds,
        )

        # Retry only transport failures. A normal remote command
        # failure is authoritative and must not be hidden.
        if result.exit_code not in {124, 255}:
            break

        if attempt < 3:
            time.sleep(1)

    assert result is not None
    return result


def _parse_json_output(stdout: str) -> dict[str, Any] | None:
    text = stdout.strip()

    if not text:
        return None

    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None

    return value if isinstance(value, dict) else None


def _discover_install_adapter() -> dict[str, Any]:
    result = _run_readonly([
        "sh",
        "-lc",
        (
            "for repo in "
            f"{APP_STORE_ROOT}/*; "
            "do "
            "[ -d \"$repo\" ] || continue; "
            "[ -d \"$repo/.git\" ] || continue; "
            "candidate=\"$repo/scripts/seymour-install-monero\"; "
            "[ -f \"$candidate\" ] || continue; "
            "[ -x \"$candidate\" ] || continue; "
            "printf '%s\\n' \"$candidate\"; "
            "done "
            "| sort "
            "| head -1"
        ),
    ])

    path = result.stdout.strip()

    return {
        "exitCode": result.exit_code,
        "path": path,
        "stderr": result.stderr,
        "available": (
            result.exit_code == 0
            and path.startswith(f"{APP_STORE_ROOT}/")
            and path.endswith("/scripts/seymour-install-monero")
        ),
    }


def _native_state(adapter_path: str) -> dict[str, Any]:
    repo = adapter_path.removesuffix(
        "/scripts/seymour-install-monero"
    )

    control = f"{repo}/scripts/seymour-umbrel-app"

    result = _run_readonly([
        control,
        "state",
        APP_ID,
    ])

    return {
        "exitCode": result.exit_code,
        "payload": _parse_json_output(result.stdout),
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def _runtime_inventory() -> dict[str, Any]:
    result = _run_readonly([
        "/usr/bin/sudo",
        "-n",
        "/usr/local/libexec/seymour-blockchain-runtime",
        "list",
    ])

    payload = _parse_json_output(result.stdout)

    matches: list[dict[str, Any]] = []

    if (
        result.exit_code == 0
        and isinstance(payload, dict)
        and isinstance(payload.get("containers"), list)
    ):
        for item in payload["containers"]:
            name = str(item.get("name") or "").lower()
            image = str(item.get("image") or "").lower()

            if (
                "seymour-monero-node" in name
                or "seymour-monero-node" in image
                or "monero" in name
                or "monero" in image
            ):
                matches.append(item)

    return {
        "available": (
            result.exit_code == 0
            and isinstance(payload, dict)
        ),
        "matches": matches,
        "payload": payload,
    }


def plan() -> dict[str, Any]:
    readiness = preflight()
    adapter = _discover_install_adapter()

    state = None

    if adapter["available"]:
        state = _native_state(adapter["path"])

    inventory = _runtime_inventory()

    runtime_absent = (
        inventory["available"]
        and len(inventory["matches"]) == 0
    )

    native_state = None

    if isinstance(state, dict):
        payload = state.get("payload")

        if isinstance(payload, dict):
            result = payload.get("result")

            if isinstance(result, dict):
                native_state = result.get("state")

    blockers: list[str] = []

    if readiness.get("ready") is not True:
        blockers.append("moneroPreflightNotReady")

    if not adapter["available"]:
        blockers.append("nativeInstallAdapterMissing")

    if not inventory["available"]:
        blockers.append("runtimeInventoryUnavailable")

    if not runtime_absent:
        blockers.append("existingMoneroRuntime")

    if native_state is None:
        blockers.append("nativeUmbrelStateUnavailable")
    elif native_state != "not-installed":
        blockers.append(
            f"nativeUmbrelState:{native_state}"
        )

    ready = len(blockers) == 0

    return {
        "mode": "plan",
        "writeOperations": False,
        "providerId": PROVIDER_ID,
        "appId": APP_ID,
        "hostAssetId": HOST_ASSET_ID,
        "preflight": readiness,
        "installAdapter": adapter,
        "nativeState": native_state,
        "runtimeInventoryAvailable": inventory["available"],
        "runtimeMatches": inventory["matches"],
        "ready": ready,
        "blockers": blockers,
        "confirmationRequired": EXECUTION_CONFIRMATION,
    }


def execute(confirmation: str) -> dict[str, Any]:
    if confirmation != EXECUTION_CONFIRMATION:
        raise ValueError(
            "Explicit confirmation is required: "
            + EXECUTION_CONFIRMATION
        )

    deployment = plan()

    if not deployment["ready"]:
        raise RuntimeError(
            "Monero installation is blocked: "
            + ", ".join(deployment["blockers"])
        )

    adapter_path = deployment["installAdapter"]["path"]

    result = _run([
        adapter_path,
        "--execute",
        "--confirm",
        NATIVE_CONFIRMATION,
    ], timeout_seconds=900)

    native_result = _parse_json_output(result.stdout)

    if result.exit_code != 0:
        return {
            "mode": "execute",
            "executed": True,
            "status": "failed",
            "providerId": PROVIDER_ID,
            "appId": APP_ID,
            "exitCode": result.exit_code,
            "result": native_result,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }

    inventory = _runtime_inventory()

    matches = inventory["matches"]

    return {
        "mode": "execute",
        "executed": True,
        "status": (
            "installed"
            if len(matches) > 0
            else "verification-pending"
        ),
        "providerId": PROVIDER_ID,
        "appId": APP_ID,
        "exitCode": result.exit_code,
        "result": native_result,
        "runtimeMatches": matches,
    }
