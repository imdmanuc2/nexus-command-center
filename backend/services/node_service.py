"""Shared blockchain-node service for the Nexus Platform APIs.

PostgreSQL persistence for blockchain_nodes is not complete yet.
Until it is, this service uses the existing shared blockchain module
directly. HomeService and other Platform services should call this
service rather than duplicating blockchain connector logic.
"""

from __future__ import annotations

from typing import Any

from backend.modules import blockchain


ONLINE_STATES = {
    "online",
    "healthy",
    "connected",
    "ready",
    "synced",
    "active",
}


def _list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [
            item
            for item in value
            if isinstance(item, dict)
        ]

    return []


def _normalize_node(
    node: dict[str, Any],
    index: int,
) -> dict[str, Any]:
    telemetry = node.get("telemetry")

    if not isinstance(telemetry, dict):
        telemetry = {}

    status = str(
        node.get("status")
        or telemetry.get("status")
        or (
            "online"
            if (
                node.get("rpcConnected")
                or telemetry.get("rpcConnected")
            )
            else "unknown"
        )
    ).lower()

    online = (
        bool(node.get("online"))
        or bool(node.get("rpcConnected"))
        or bool(telemetry.get("rpcConnected"))
        or status in ONLINE_STATES
    )

    return {
        "nodeId": str(
            node.get("nodeId")
            or node.get("id")
            or node.get("assetId")
            or node.get("host")
            or node.get("ip")
            or f"blockchain-node-{index + 1}"
        ),
        "assetId": node.get("assetId"),
        "name": (
            node.get("name")
            or node.get("displayName")
            or node.get("implementation")
            or "Blockchain Node"
        ),
        "coin": (
            node.get("coin")
            or node.get("symbol")
            or telemetry.get("coin")
            or telemetry.get("chain")
            or ""
        ),
        "network": (
            node.get("network")
            or telemetry.get("chain")
            or ""
        ),
        "implementation": (
            node.get("implementation")
            or telemetry.get("implementation")
            or node.get("name")
            or ""
        ),
        "version": (
            node.get("version")
            or telemetry.get("version")
            or telemetry.get("subversion")
            or ""
        ),
        "host": (
            node.get("host")
            or node.get("ip")
            or node.get("address")
            or telemetry.get("host")
            or ""
        ),
        "status": "online" if online else status,
        "online": online,
        "rpcConnected": (
            bool(node.get("rpcConnected"))
            or bool(telemetry.get("rpcConnected"))
        ),
        "syncStatus": (
            node.get("syncStatus")
            or telemetry.get("syncStatus")
            or (
                "synced"
                if (
                    telemetry.get("initialBlockDownload") is False
                    or telemetry.get("ibd") is False
                )
                else "unknown"
            )
        ),
        "syncPercent": (
            node.get("syncPercent")
            or telemetry.get("syncPercent")
            or telemetry.get("verificationProgress")
        ),
        "blockHeight": (
            node.get("blockHeight")
            or telemetry.get("blockHeight")
            or telemetry.get("blocks")
        ),
        "headers": (
            node.get("headers")
            or node.get("headerHeight")
            or telemetry.get("headers")
        ),
        "peers": (
            node.get("peers")
            or node.get("peerCount")
            or telemetry.get("peers")
            or telemetry.get("connections")
        ),
        "diskBytes": (
            node.get("diskBytes")
            or telemetry.get("diskBytes")
            or telemetry.get("sizeOnDisk")
        ),
        "mempoolTransactions": (
            node.get("mempoolTransactions")
            or telemetry.get("mempoolTransactions")
            or telemetry.get("mempoolSize")
        ),
        "lastSeenAt": (
            node.get("lastSeenAt")
            or telemetry.get("observedAt")
            or telemetry.get("updatedAt")
        ),
        "observedState": node,
    }


def nodes() -> dict[str, Any]:
    payload = blockchain.nodes()

    if not isinstance(payload, dict):
        payload = {}

    records = _list(payload.get("nodes"))

    if not records:
        records = _list(payload.get("items"))

    if not records:
        records = _list(payload.get("blockchainNodes"))

    single = payload.get("node")

    if not records and isinstance(single, dict):
        records = [single]

    # Some existing implementations return node fields at the root.
    if (
        not records
        and (
            payload.get("rpcConnected") is not None
            or payload.get("blockHeight") is not None
            or payload.get("telemetry") is not None
        )
    ):
        records = [payload]

    normalized = [
        _normalize_node(node, index)
        for index, node in enumerate(records)
    ]

    online_count = sum(
        1
        for node in normalized
        if node["online"]
    )

    return {
        "status": "ok",
        "source": "nexus-shared-blockchain-service",
        "count": len(normalized),
        "onlineCount": online_count,
        "offlineCount": len(normalized) - online_count,
        "nodes": normalized,
    }
