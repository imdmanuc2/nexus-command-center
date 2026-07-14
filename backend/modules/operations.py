#!/usr/bin/env python3

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable

from backend.modules import blockchain
from backend.modules import mining_readiness


ActionHandler = Callable[[dict[str, Any]], dict[str, Any]]

_ACTIONS: dict[str, dict[str, Any]] = {}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _step(
    name: str,
    status: str,
    summary: str = "",
    details: Any = None,
    duration_ms: int = 0,
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "name": name,
        "status": status,
        "summary": summary,
        "durationMs": duration_ms,
    }

    if details is not None:
        item["details"] = details

    return item


def register(
    action: str,
    handler: ActionHandler,
    *,
    label: str,
    description: str,
    category: str,
    target_type: str,
    read_only: bool = True,
    confirmation_required: bool = False,
) -> None:
    if not action:
        raise ValueError("Action name is required")

    if action in _ACTIONS:
        raise ValueError(f"Action already registered: {action}")

    _ACTIONS[action] = {
        "action": action,
        "label": label,
        "description": description,
        "category": category,
        "targetType": target_type,
        "readOnly": read_only,
        "confirmationRequired": confirmation_required,
        "handler": handler,
    }


def available() -> dict[str, Any]:
    items = []

    for name in sorted(_ACTIONS):
        definition = _ACTIONS[name]

        items.append({
            "action": definition["action"],
            "label": definition["label"],
            "description": definition["description"],
            "category": definition["category"],
            "targetType": definition["targetType"],
            "readOnly": definition["readOnly"],
            "confirmationRequired": definition["confirmationRequired"],
        })

    return {
        "status": "online",
        "count": len(items),
        "items": items,
    }


def run(action: str, target: dict[str, Any] | None = None) -> dict[str, Any]:
    target = target or {}

    definition = _ACTIONS.get(action)

    if definition is None:
        return {
            "runId": f"operation-{uuid.uuid4()}",
            "action": action,
            "status": "error",
            "message": f"Unknown operation: {action}",
            "target": target,
            "startedAt": _iso_now(),
            "completedAt": _iso_now(),
            "durationMs": 0,
            "steps": [],
        }

    run_id = f"operation-{uuid.uuid4()}"
    started_iso = _iso_now()
    started_monotonic = time.perf_counter()

    try:
        result = definition["handler"](target)

        if not isinstance(result, dict):
            raise TypeError(
                f"Operation handler {action} returned "
                f"{type(result).__name__}; expected dict"
            )

        status = result.get("status", "unknown")
        steps = result.get("steps", [])
        summary = result.get("summary", "")

    except Exception as exc:
        status = "error"
        summary = str(exc)
        steps = [
            _step(
                "Execute operation",
                "fail",
                "The operation raised an unexpected error.",
                details=str(exc),
            )
        ]

    completed_iso = _iso_now()
    duration_ms = round(
        (time.perf_counter() - started_monotonic) * 1000
    )

    return {
        "runId": run_id,
        "action": action,
        "label": definition["label"],
        "description": definition["description"],
        "category": definition["category"],
        "targetType": definition["targetType"],
        "target": target,
        "status": status,
        "summary": summary,
        "readOnly": definition["readOnly"],
        "confirmationRequired": definition["confirmationRequired"],
        "startedAt": started_iso,
        "completedAt": completed_iso,
        "durationMs": duration_ms,
        "steps": steps,
    }


def _find_blockchain_node(
    nodes_payload: dict[str, Any],
    target: dict[str, Any],
) -> dict[str, Any] | None:
    items = nodes_payload.get("items", [])

    if not isinstance(items, list):
        return None

    asset_id = str(target.get("assetId", "")).strip()
    host = str(target.get("host", "")).strip()
    coin = str(target.get("coin", "")).strip().upper()

    if asset_id:
        for node in items:
            if str(node.get("assetId", "")) == asset_id:
                return node

    if host:
        for node in items:
            if str(node.get("host", "")) == host:
                return node

    if coin:
        for node in items:
            if str(node.get("coin", "")).upper() == coin:
                return node

    if len(items) == 1:
        return items[0]

    return None


def bitcoin_rpc_test(target: dict[str, Any]) -> dict[str, Any]:
    steps: list[dict[str, Any]] = []

    lookup_started = time.perf_counter()

    nodes_payload = blockchain.nodes()

    lookup_duration = round(
        (time.perf_counter() - lookup_started) * 1000
    )

    node = _find_blockchain_node(nodes_payload, target)

    if node is None:
        steps.append(
            _step(
                "Resolve blockchain node",
                "fail",
                "Nexus could not resolve the requested blockchain node.",
                details={
                    "assetId": target.get("assetId"),
                    "host": target.get("host"),
                    "coin": target.get("coin"),
                    "availableNodes": nodes_payload.get("count", 0),
                },
                duration_ms=lookup_duration,
            )
        )

        return {
            "status": "fail",
            "summary": "Blockchain node could not be resolved.",
            "steps": steps,
        }

    node_name = node.get("name") or node.get("host") or "Blockchain node"
    host = node.get("host")
    rpc_port = node.get("rpcPort")

    steps.append(
        _step(
            "Resolve blockchain node",
            "pass",
            f"Resolved {node_name}.",
            details={
                "assetId": node.get("assetId"),
                "name": node_name,
                "coin": node.get("coin"),
                "host": host,
                "rpcPort": rpc_port,
            },
            duration_ms=lookup_duration,
        )
    )

    rpc_connected = bool(node.get("rpcConnected"))

    steps.append(
        _step(
            "Connect to RPC endpoint",
            "pass" if rpc_connected else "fail",
            (
                f"RPC responded at {host}:{rpc_port}."
                if rpc_connected
                else f"RPC did not respond at {host}:{rpc_port}."
            ),
            details={
                "rpcStatus": node.get("rpcStatus"),
                "checkedAt": node.get("checkedAt"),
            },
        )
    )

    if not rpc_connected:
        return {
            "status": "fail",
            "summary": f"RPC connectivity failed for {node_name}.",
            "steps": steps,
        }

    version = node.get("version")
    subversion = node.get("subversion")
    protocol_version = node.get("protocolVersion")

    steps.append(
        _step(
            "Verify RPC identity",
            "pass" if version or subversion else "warn",
            subversion or "RPC responded without version identity.",
            details={
                "version": version,
                "subversion": subversion,
                "protocolVersion": protocol_version,
            },
        )
    )

    chain = node.get("chain")
    chain_status = "pass" if chain == "main" else "warn"

    steps.append(
        _step(
            "Verify blockchain network",
            chain_status,
            (
                "Node is connected to Bitcoin mainnet."
                if chain == "main"
                else f"Node reports blockchain network: {chain or 'unknown'}."
            ),
            details={
                "chain": chain,
                "bestBlockHash": node.get("bestBlockHash"),
                "difficulty": node.get("difficulty"),
            },
        )
    )

    blocks = node.get("blocks", node.get("blockHeight"))
    headers = node.get("headers")
    sync_percent = node.get("syncPercent")
    initial_block_download = bool(node.get("initialBlockDownload"))

    sync_ok = (
        blocks is not None
        and headers is not None
        and int(blocks) >= int(headers)
        and not initial_block_download
    )

    sync_status = "pass" if sync_ok else "warn"

    steps.append(
        _step(
            "Verify blockchain synchronization",
            sync_status,
            (
                f"Blockchain synchronized at {sync_percent:.6f}%."
                if isinstance(sync_percent, (int, float))
                else "Blockchain synchronization status received."
            ),
            details={
                "blocks": blocks,
                "headers": headers,
                "syncPercent": sync_percent,
                "verificationProgress": node.get(
                    "verificationProgress"
                ),
                "initialBlockDownload": initial_block_download,
            },
        )
    )

    peer_count = node.get(
        "peerCount",
        node.get("peers", node.get("connections", 0)),
    )

    try:
        peers_ok = int(peer_count or 0) > 0
    except (TypeError, ValueError):
        peers_ok = False

    steps.append(
        _step(
            "Verify peer connectivity",
            "pass" if peers_ok else "warn",
            (
                f"{peer_count} blockchain peers connected."
                if peers_ok
                else "No connected blockchain peers were reported."
            ),
            details={
                "peerCount": peer_count,
                "networkActive": node.get("networkActive"),
            },
        )
    )

    mempool_size = node.get("mempoolSize")
    mempool_bytes = node.get("mempoolBytes")

    steps.append(
        _step(
            "Verify mempool access",
            "pass" if mempool_size is not None else "warn",
            (
                f"Mempool contains {mempool_size} transactions."
                if mempool_size is not None
                else "Mempool information was not returned."
            ),
            details={
                "transactions": mempool_size,
                "bytes": mempool_bytes,
                "usage": node.get("mempoolUsage"),
                "maximumBytes": node.get("mempoolMax"),
            },
        )
    )

    disk_size = node.get("sizeOnDisk")

    steps.append(
        _step(
            "Verify blockchain storage",
            "pass" if disk_size is not None else "warn",
            (
                "Blockchain storage information is available."
                if disk_size is not None
                else "Blockchain storage information was not returned."
            ),
            details={
                "sizeOnDisk": disk_size,
                "pruned": node.get("pruned"),
            },
        )
    )

    failed_steps = [
        step for step in steps
        if step.get("status") == "fail"
    ]

    warning_steps = [
        step for step in steps
        if step.get("status") == "warn"
    ]

    if failed_steps:
        overall_status = "fail"
        summary = f"RPC test failed for {node_name}."
    elif warning_steps:
        overall_status = "warn"
        summary = (
            f"RPC test completed for {node_name} "
            f"with {len(warning_steps)} warning(s)."
        )
    else:
        overall_status = "pass"
        summary = f"RPC test passed for {node_name}."

    return {
        "status": overall_status,
        "summary": summary,
        "steps": steps,
    }


def _find_pool_readiness(
    readiness_payload: dict[str, Any],
    target: dict[str, Any],
) -> dict[str, Any] | None:
    items = readiness_payload.get("items", [])

    if not isinstance(items, list):
        return None

    asset_id = str(target.get("assetId", "")).strip()
    pool_node_id = str(target.get("poolNodeId", "")).strip()
    pool_id = str(target.get("poolId", "")).strip()
    host = str(target.get("host", "")).strip()
    coin = str(target.get("coin", "")).strip().upper()

    requested_node_id = pool_node_id or asset_id

    if requested_node_id:
        for pool in items:
            if str(pool.get("poolNodeId", "")) == requested_node_id:
                return pool

    if host and pool_id:
        for pool in items:
            if (
                str(pool.get("host", "")) == host
                and str(pool.get("poolId", "")) == pool_id
            ):
                return pool

    if host:
        host_matches = [
            pool
            for pool in items
            if str(pool.get("host", "")) == host
        ]

        if len(host_matches) == 1:
            return host_matches[0]

    if pool_id:
        pool_matches = [
            pool
            for pool in items
            if str(pool.get("poolId", "")) == pool_id
        ]

        if len(pool_matches) == 1:
            return pool_matches[0]

        if coin:
            for pool in pool_matches:
                if str(pool.get("coin", "")).upper() == coin:
                    return pool

    if len(items) == 1:
        return items[0]

    return None


def miningcore_pool_readiness(
    target: dict[str, Any],
) -> dict[str, Any]:
    lookup_started = time.perf_counter()
    readiness_payload = mining_readiness.pools()
    lookup_duration = round(
        (time.perf_counter() - lookup_started) * 1000
    )

    selected = _find_pool_readiness(readiness_payload, target)

    if selected is None:
        return {
            "status": "fail",
            "summary": "Pool could not be resolved.",
            "steps": [
                _step(
                    "Resolve mining pool",
                    "fail",
                    "Nexus could not resolve the requested mining pool.",
                    details={
                        "assetId": target.get("assetId"),
                        "poolNodeId": target.get("poolNodeId"),
                        "poolId": target.get("poolId"),
                        "host": target.get("host"),
                        "coin": target.get("coin"),
                        "availablePools": readiness_payload.get(
                            "count", 0
                        ),
                    },
                    duration_ms=lookup_duration,
                )
            ],
        }

    pool_name = (
        selected.get("name")
        or selected.get("poolId")
        or "Mining pool"
    )

    steps: list[dict[str, Any]] = [
        _step(
            "Resolve mining pool",
            "pass",
            f"Resolved {pool_name}.",
            details={
                "poolNodeId": selected.get("poolNodeId"),
                "poolId": selected.get("poolId"),
                "name": pool_name,
                "host": selected.get("host"),
                "coin": selected.get("coin"),
                "mode": selected.get("mode"),
                "status": selected.get("status"),
                "readinessScore": selected.get("readinessScore"),
                "readyToMine": selected.get("readyToMine"),
                "activeMining": selected.get("activeMining"),
            },
            duration_ms=lookup_duration,
        )
    ]

    status_map = {
        "healthy": "pass",
        "warning": "warn",
        "failed": "fail",
        "pass": "pass",
        "warn": "warn",
        "fail": "fail",
    }

    checks = selected.get("checks", [])

    if not isinstance(checks, list):
        checks = []

    for check in checks:
        raw_status = str(check.get("status", "warning")).lower()
        step_status = status_map.get(raw_status, "warn")

        steps.append(
            _step(
                str(check.get("label") or "Readiness check"),
                step_status,
                str(
                    check.get("detail")
                    or "No readiness detail was returned."
                ),
                details={
                    "key": check.get("key"),
                    "required": bool(check.get("required")),
                    "sourceStatus": raw_status,
                },
            )
        )

    if not checks:
        steps.append(
            _step(
                "Load readiness checks",
                "warn",
                "No detailed pool readiness checks were returned.",
            )
        )

    failed_required = any(
        step.get("status") == "fail"
        and bool(step.get("details", {}).get("required"))
        for step in steps
    )
    failed_any = any(
        step.get("status") == "fail"
        for step in steps
    )
    warned_any = any(
        step.get("status") == "warn"
        for step in steps
    )

    ready_to_mine = bool(selected.get("readyToMine"))
    readiness_score = selected.get("readinessScore")

    if failed_required or failed_any:
        overall_status = "fail"
    elif ready_to_mine and not warned_any:
        overall_status = "pass"
    elif ready_to_mine or warned_any:
        overall_status = "warn"
    else:
        overall_status = "fail"

    recommendation = str(
        selected.get("recommendation")
        or "Pool readiness assessment completed."
    )

    if overall_status == "pass":
        summary = f"Pool readiness passed for {pool_name}."
    elif overall_status == "warn":
        summary = (
            f"Pool readiness completed for {pool_name} with warnings. "
            f"{recommendation}"
        )
    else:
        summary = (
            f"Pool readiness failed for {pool_name}. "
            f"{recommendation}"
        )

    return {
        "status": overall_status,
        "summary": summary,
        "steps": steps,
        "metadata": {
            "poolNodeId": selected.get("poolNodeId"),
            "poolId": selected.get("poolId"),
            "name": pool_name,
            "host": selected.get("host"),
            "coin": selected.get("coin"),
            "mode": selected.get("mode"),
            "readinessScore": readiness_score,
            "readyToMine": ready_to_mine,
            "activeMining": selected.get("activeMining"),
            "connectedMiners": selected.get("connectedMiners"),
            "hashrate": selected.get("hashrate"),
            "sharesPerSecond": selected.get("sharesPerSecond"),
            "stratumPorts": selected.get("stratumPorts", []),
            "blockchainAssetId": selected.get("blockchainAssetId"),
            "blockchainName": selected.get("blockchainName"),
            "blockHeight": selected.get("blockHeight"),
            "peerCount": selected.get("peerCount"),
            "recommendation": recommendation,
            "checkedAt": selected.get("checkedAt"),
        },
    }


register(
    "bitcoin.rpc.test",
    bitcoin_rpc_test,
    label="Test RPC",
    description=(
        "Verify credentials, RPC access, node identity, chain, "
        "synchronization, peers, mempool, and blockchain storage."
    ),
    category="bitcoin",
    target_type="blockchain-node",
    read_only=True,
    confirmation_required=False,
)

register(
    "miningcore.pool.readiness",
    miningcore_pool_readiness,
    label="Pool Readiness Assessment",
    description=(
        "Verify MiningCore API, blockchain RPC, synchronization, "
        "networking, stratum, connected miners, hashrate, and share flow."
    ),
    category="pool",
    target_type="pool",
    read_only=True,
    confirmation_required=False,
)