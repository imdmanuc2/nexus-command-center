"""Nexus blockchain node telemetry.

RPC credentials are read from environment variables. Passwords are never
returned by the API.

The endpoint is intentionally cached so opening the Digital Twin does not
hammer blockchain nodes.
"""

from __future__ import annotations

import base64
import json
import os
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


CONFIG_FILE = Path("backend/data/config/blockchain_nodes.json")
CACHE_SECONDS = 10

_cache_lock = threading.Lock()
_cache: dict[str, Any] = {
    "expiresAt": 0.0,
    "payload": None,
}


def _now_ms() -> int:
    return int(time.time() * 1000)


def _load_config() -> list[dict[str, Any]]:
    if not CONFIG_FILE.exists():
        return []

    try:
        payload = json.loads(CONFIG_FILE.read_text() or "{}")
    except (OSError, json.JSONDecodeError):
        return []

    nodes = payload.get("nodes", [])

    if not isinstance(nodes, list):
        return []

    return [
        node
        for node in nodes
        if isinstance(node, dict)
        and node.get("enabled", True)
    ]


def _rpc_credentials(node: dict[str, Any]) -> tuple[str, str]:
    user_env = str(
        node.get("rpcUserEnv")
        or "NEXUS_BTC_RPC_USER"
    )

    password_env = str(
        node.get("rpcPasswordEnv")
        or "NEXUS_BTC_RPC_PASSWORD"
    )

    user = os.environ.get(user_env, "")
    password = os.environ.get(password_env, "")

    return user, password


def _rpc_call(
    node: dict[str, Any],
    method: str,
    params: list[Any] | None = None,
    *,
    timeout: float = 4.0,
) -> Any:
    host = str(node.get("host") or "").strip()
    port = int(node.get("rpcPort") or 8332)
    user, password = _rpc_credentials(node)

    if not host:
        raise RuntimeError("RPC host is missing.")

    if not user or not password:
        raise RuntimeError(
            "RPC credentials are not configured in the Nexus service environment."
        )

    body = json.dumps({
        "jsonrpc": "1.0",
        "id": "nexus-command-center",
        "method": method,
        "params": params or [],
    }).encode("utf-8")

    token = base64.b64encode(
        f"{user}:{password}".encode("utf-8")
    ).decode("ascii")

    request = urllib.request.Request(
        f"http://{host}:{port}/",
        data=body,
        method="POST",
        headers={
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Nexus-Command-Center/1.0",
        },
    )

    try:
        with urllib.request.urlopen(
            request,
            timeout=timeout,
        ) as response:
            payload = json.loads(
                response.read().decode("utf-8")
            )
    except urllib.error.HTTPError as error:
        if error.code == 401:
            raise RuntimeError(
                "Bitcoin RPC rejected the configured credentials."
            ) from error

        raise RuntimeError(
            f"Bitcoin RPC returned HTTP {error.code}."
        ) from error
    except urllib.error.URLError as error:
        raise RuntimeError(
            f"Unable to connect to Bitcoin RPC: {error.reason}"
        ) from error
    except TimeoutError as error:
        raise RuntimeError(
            "Bitcoin RPC request timed out."
        ) from error

    if payload.get("error"):
        error = payload["error"]
        message = (
            error.get("message")
            if isinstance(error, dict)
            else str(error)
        )

        raise RuntimeError(
            f"Bitcoin RPC error: {message}"
        )

    return payload.get("result")


def _sync_percent(blockchain: dict[str, Any]) -> float:
    progress = float(
        blockchain.get("verificationprogress") or 0
    )

    return round(progress * 100, 6)


def _node_status(node: dict[str, Any]) -> dict[str, Any]:
    asset_id = str(node.get("assetId") or "")
    name = str(node.get("name") or asset_id or "Blockchain Node")
    host = str(node.get("host") or "")
    rpc_port = int(node.get("rpcPort") or 8332)
    coin = str(node.get("coin") or "BTC").upper()

    base = {
        "assetId": asset_id,
        "name": name,
        "coin": coin,
        "host": host,
        "rpcPort": rpc_port,
        "rpcConnected": False,
        "rpcStatus": "disconnected",
        "checkedAt": _now_ms(),
    }

    try:
        blockchain = _rpc_call(
            node,
            "getblockchaininfo",
        )

        network = _rpc_call(
            node,
            "getnetworkinfo",
        )

        mempool = _rpc_call(
            node,
            "getmempoolinfo",
        )

        try:
            peer_info = _rpc_call(
                node,
                "getpeerinfo",
            )
            peer_count = len(peer_info or [])
        except RuntimeError:
            peer_count = int(
                network.get("connections") or 0
            )

        blocks = int(
            blockchain.get("blocks") or 0
        )

        headers = int(
            blockchain.get("headers") or 0
        )

        return {
            **base,
            "rpcConnected": True,
            "rpcStatus": "connected",
            "status": "online",
            "chain": blockchain.get("chain"),
            "blocks": blocks,
            "blockHeight": blocks,
            "headers": headers,
            "verificationProgress": float(
                blockchain.get("verificationprogress") or 0
            ),
            "syncPercent": _sync_percent(blockchain),
            "initialBlockDownload": bool(
                blockchain.get("initialblockdownload", False)
            ),
            "bestBlockHash": blockchain.get("bestblockhash"),
            "difficulty": blockchain.get("difficulty"),
            "chainWork": blockchain.get("chainwork"),
            "sizeOnDisk": blockchain.get("size_on_disk"),
            "pruned": bool(blockchain.get("pruned", False)),
            "warnings": blockchain.get("warnings") or "",
            "connections": peer_count,
            "peers": peer_count,
            "peerCount": peer_count,
            "version": network.get("version"),
            "subversion": network.get("subversion"),
            "protocolVersion": network.get("protocolversion"),
            "networkActive": network.get("networkactive"),
            "relayFee": network.get("relayfee"),
            "incrementalFee": network.get("incrementalfee"),
            "mempoolSize": int(mempool.get("size") or 0),
            "mempoolBytes": int(mempool.get("bytes") or 0),
            "mempoolUsage": int(mempool.get("usage") or 0),
            "mempoolMax": int(mempool.get("maxmempool") or 0),
            "checkedAt": _now_ms(),
        }

    except Exception as error:
        return {
            **base,
            "status": "warning",
            "error": str(error),
            "checkedAt": _now_ms(),
        }


def _fresh_payload() -> dict[str, Any]:
    configured_nodes = _load_config()
    items = [
        _node_status(node)
        for node in configured_nodes
    ]

    connected = sum(
        1
        for item in items
        if item.get("rpcConnected") is True
    )

    return {
        "status": (
            "online"
            if items and connected == len(items)
            else "warning"
            if items
            else "empty"
        ),
        "timestamp": _now_ms(),
        "count": len(items),
        "connected": connected,
        "items": items,
    }


def nodes() -> dict[str, Any]:
    now = time.monotonic()

    with _cache_lock:
        cached = _cache.get("payload")

        if (
            cached is not None
            and now < float(_cache.get("expiresAt") or 0)
        ):
            return cached

    payload = _fresh_payload()

    with _cache_lock:
        _cache["payload"] = payload
        _cache["expiresAt"] = (
            time.monotonic() + CACHE_SECONDS
        )

    return payload


def clear_cache() -> dict[str, Any]:
    with _cache_lock:
        _cache["payload"] = None
        _cache["expiresAt"] = 0.0

    return {
        "status": "cleared",
    }
