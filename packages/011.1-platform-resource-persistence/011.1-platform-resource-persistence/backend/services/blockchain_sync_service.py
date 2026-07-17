"""Synchronize live blockchain-node state into PostgreSQL."""

from __future__ import annotations

from typing import Any

from backend.db.repositories.blockchain_repository import (
    mark_stale_blockchain_nodes,
    upsert_blockchain_node,
)
from backend.services.resource_sync_common import (
    fetch_json,
    stable_id,
)


def _candidate_nodes(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [
            item
            for item in payload
            if isinstance(item, dict)
        ]

    if not isinstance(payload, dict):
        return []

    for key in ("nodes", "items", "assets", "data"):
        value = payload.get(key)

        if isinstance(value, list):
            return [
                item
                for item in value
                if isinstance(item, dict)
            ]

    if any(
        key in payload
        for key in (
            "rpcConnected",
            "blockHeight",
            "blocks",
            "headers",
            "ip",
            "name",
            "coin",
        )
    ):
        return [payload]

    for value in payload.values():
        if not isinstance(value, dict):
            continue

        if any(
            key in value
            for key in (
                "rpcConnected",
                "blockHeight",
                "blocks",
                "headers",
            )
        ):
            return [value]

    return []


def _percent(value: Any) -> float | None:
    if value is None:
        return None

    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None

    if 0 <= numeric <= 1:
        return numeric * 100

    return numeric


def synchronize_blockchain_nodes(
    stale_seconds: int = 300,
) -> dict[str, Any]:
    payload = fetch_json("/api/blockchain/nodes")
    candidates = _candidate_nodes(payload)
    written: list[dict[str, Any]] = []

    for raw in candidates:
        name = str(
            raw.get("name")
            or raw.get("friendlyName")
            or raw.get("displayName")
            or "Blockchain Node"
        )

        ip_address = str(
            raw.get("ip")
            or raw.get("host")
            or ""
        )

        coin = str(
            raw.get("coin")
            or raw.get("symbol")
            or "BTC"
        ).upper()

        chain = str(
            raw.get("chain")
            or raw.get("network")
            or "main"
        )

        asset_id = str(
            raw.get("assetId")
            or raw.get("id")
            or stable_id(
                "asset",
                coin,
                ip_address,
                name,
            )
        )

        node_id = str(
            raw.get("nodeId")
            or asset_id
        )

        rpc_connected = bool(
            raw.get("rpcConnected")
            or str(
                raw.get("rpcStatus") or ""
            ).lower()
            in {
                "online",
                "connected",
                "healthy",
            }
        )

        status = str(
            raw.get("status")
            or (
                "online"
                if rpc_connected
                else "offline"
            )
        )

        written.append(
            upsert_blockchain_node(
                {
                    "asset_id": asset_id,
                    "node_id": node_id,
                    "name": name,
                    "coin": coin,
                    "chain": chain,
                    "host": str(
                        raw.get("host")
                        or ip_address
                    ),
                    "ip_address": ip_address,
                    "rpc_port": (
                        raw.get("rpcPort")
                        or 8332
                    ),
                    "p2p_port": (
                        raw.get("p2pPort")
                        or 8333
                    ),
                    "rpc_connected": rpc_connected,
                    "status": status,
                    "version": str(
                        raw.get("version")
                        or raw.get("subversion")
                        or ""
                    ),
                    "block_height": (
                        raw.get("blockHeight")
                        or raw.get("blocks")
                    ),
                    "header_height": (
                        raw.get("headerHeight")
                        or raw.get("headers")
                    ),
                    "sync_percent": _percent(
                        raw.get("syncPercent")
                        or raw.get("verificationProgress")
                    ),
                    "peer_count": (
                        raw.get("peerCount")
                        or raw.get("peers")
                    ),
                    "mempool_transactions": (
                        raw.get("mempoolTransactions")
                        or raw.get("mempoolTx")
                    ),
                    "disk_usage_bytes": (
                        raw.get("diskUsageBytes")
                        or raw.get("diskUsage")
                    ),
                    "raw_payload": raw,
                }
            )
        )

    marked_offline = mark_stale_blockchain_nodes(
        stale_seconds
    )

    return {
        "status": "ok",
        "source": "blockchain-resource-sync",
        "observed": len(candidates),
        "written": len(written),
        "markedOffline": marked_offline,
        "nodes": written,
    }
