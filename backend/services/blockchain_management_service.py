from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CATALOG_FILE = Path(
    "backend/data/config/blockchain_provider_catalog.json"
)

# Nexus architecture rule:
# The CMDB is the canonical source of truth for managed infrastructure.
# Discovery, telemetry, registration, transport, and runtime observers
# provide evidence that must be reconciled into CMDB state. Blockchain
# management must not establish a competing inventory/source of truth.
CMDB_CANONICAL_SOURCE = True


def _load_catalog() -> dict[str, Any]:
    if not CATALOG_FILE.exists():
        raise RuntimeError(
            "Blockchain provider catalog is not configured."
        )

    payload = json.loads(
        CATALOG_FILE.read_text(encoding="utf-8")
    )

    providers = payload.get("providers")

    if not isinstance(providers, list):
        raise RuntimeError(
            "Blockchain provider catalog providers must be a list."
        )

    return payload


def catalog() -> dict[str, Any]:
    payload = _load_catalog()

    providers = [
        provider
        for provider in payload["providers"]
        if isinstance(provider, dict)
        and provider.get("enabled", True)
    ]

    return {
        "status": "ok",
        "schemaVersion": payload.get("schemaVersion", 1),
        "count": len(providers),
        "providers": providers,
    }


def _provider(provider_id: str) -> dict[str, Any]:
    provider_id = str(provider_id or "").strip()

    for provider in catalog()["providers"]:
        if provider.get("providerId") == provider_id:
            return provider

    raise ValueError(
        f"Unknown blockchain provider: {provider_id}"
    )


def create_deployment_plan(
    request: dict[str, Any],
) -> dict[str, Any]:
    provider_id = str(
        request.get("providerId") or ""
    ).strip()

    host_asset_id = str(
        request.get("hostAssetId") or ""
    ).strip()

    if not provider_id:
        raise ValueError("providerId is required.")

    if not host_asset_id:
        raise ValueError("hostAssetId is required.")

    provider = _provider(provider_id)

    if provider.get("availability") != "live":
        raise ValueError(
            f"Blockchain provider is not available for deployment: {provider_id}"
        )

    if not provider.get("selectable", False):
        raise ValueError(
            f"Blockchain provider is not selectable for deployment: {provider_id}"
        )

    storage_request = request.get("storage") or {}

    if not isinstance(storage_request, dict):
        raise ValueError("storage must be an object.")

    selection_mode = str(
        storage_request.get("selectionMode")
        or "discovered"
    ).strip()

    if selection_mode not in {
        "discovered",
        "custom",
    }:
        raise ValueError(
            "storage.selectionMode must be discovered or custom."
        )

    target_id = str(
        storage_request.get("targetId") or ""
    ).strip()

    custom_path = str(
        storage_request.get("path") or ""
    ).strip()

    if selection_mode == "discovered" and not target_id:
        raise ValueError(
            "storage.targetId is required for discovered storage."
        )

    if selection_mode == "custom" and not custom_path:
        raise ValueError(
            "storage.path is required for custom storage."
        )

    defaults = provider.get("defaultPorts") or {}
    requested_network = request.get("network") or {}

    if not isinstance(requested_network, dict):
        raise ValueError("network must be an object.")

    p2p_port = int(
        requested_network.get("p2pPort")
        or defaults.get("p2p")
        or 0
    )

    rpc_port = int(
        requested_network.get("rpcPort")
        or defaults.get("rpc")
        or 0
    )

    for name, value in (
        ("p2pPort", p2p_port),
        ("rpcPort", rpc_port),
    ):
        if value < 1 or value > 65535:
            raise ValueError(
                f"network.{name} must be between 1 and 65535."
            )

    if p2p_port == rpc_port:
        raise ValueError(
            "P2P and RPC ports must be different."
        )

    return {
        "status": "planned",
        "provider": {
            "providerId": provider["providerId"],
            "coin": provider["coin"],
            "name": provider["name"],
            "network": provider["network"],
            "implementation": provider["implementation"],
        },
        "hostAssetId": host_asset_id,
        "storage": {
            "selectionMode": selection_mode,
            "targetId": (
                target_id
                if selection_mode == "discovered"
                else None
            ),
            "customPath": (
                custom_path
                if selection_mode == "custom"
                else None
            ),
            "directoryName": (
                provider.get("storage") or {}
            ).get("directoryName"),
            "minimumFreeBytes": (
                provider.get("storage") or {}
            ).get("minimumFreeBytes"),
        },
        "network": {
            "p2pPort": p2p_port,
            "rpcPort": rpc_port,
        },
        "requirements": {
            "architectures": provider.get(
                "architectures",
                [],
            ),
        },
        "preflight": {
            "hostReachable": None,
            "architectureSupported": None,
            "storageWritable": None,
            "capacitySufficient": None,
            "portsAvailable": None,
        },
        "executable": False,
        "executionBlockedReason": (
            "Package 074 creates deployment plans only. "
            "Remote blockchain installation is not enabled."
        ),
    }
