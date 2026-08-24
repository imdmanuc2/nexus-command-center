"""Canonical provider-neutral blockchain runtime health model."""

from __future__ import annotations

from typing import Any


SYNCED_THRESHOLD = 99.999


def _text(value: Any) -> str:
    return str(value or "").strip().lower()


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bool(value: Any) -> bool | None:
    if value is None:
        return None

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return bool(value)

    normalized = _text(value)

    if normalized in {"1", "true", "yes", "on"}:
        return True

    if normalized in {"0", "false", "no", "off"}:
        return False

    return None


def derive_blockchain_runtime_health(
    observation: dict[str, Any],
) -> dict[str, Any]:
    """Derive independent blockchain runtime health dimensions.

    The dimensions deliberately remain separate:

    runtimeState
        Is the blockchain process/runtime operating?

    connectivityState
        Can Nexus currently reach the blockchain runtime?

    syncState
        Is the local chain caught up to the network?

    rpcState
        Can dependent services safely use the RPC interface?

    miningReadiness
        Is there enough authoritative evidence to use this node
        for a mining pool?

    overallState
        Human-facing operational summary derived from the above.
    """

    running = _bool(observation.get("running"))

    node_status = _text(
        observation.get("nodeStatus")
        or observation.get("status")
    )

    lifecycle_status = _text(
        observation.get("lifecycleStatus")
    )

    sync_status = _text(
        observation.get("syncStatus")
    )

    sync_progress = _number(
        observation.get("syncProgress")
    )

    if sync_progress is None:
        sync_progress = _number(
            observation.get("syncPercent")
        )

    block_height = _number(
        observation.get("blockHeight")
    )

    header_height = _number(
        observation.get("headerHeight")
    )

    initial_block_download = _bool(
        observation.get("initialBlockDownload")
    )

    rpc_reachable = _bool(
        observation.get("rpcReachable")
    )

    rpc_healthy = _bool(
        observation.get("rpcHealthy")
    )

    rpc_connected = _bool(
        observation.get("rpcConnected")
    )

    sync_stalled = _bool(
        observation.get("syncStalled")
    )

    #
    # Runtime
    #

    if node_status in {"failed", "error"}:
        runtime_state = "failed"
    elif lifecycle_status in {
        "starting",
        "restarting",
        "stopping",
    }:
        runtime_state = lifecycle_status
    elif running is True:
        runtime_state = "running"
    elif running is False:
        runtime_state = "stopped"
    elif node_status in {
        "running",
        "online",
        "syncing",
        "synced",
    }:
        runtime_state = "running"
    elif node_status in {"stopped", "offline"}:
        runtime_state = "stopped"
    else:
        runtime_state = "unknown"

    #
    # Connectivity
    #

    if rpc_reachable is True or rpc_connected is True:
        connectivity_state = "online"
    elif node_status == "online":
        connectivity_state = "online"
    elif (
        rpc_reachable is False
        or rpc_connected is False
    ):
        connectivity_state = "unreachable"
    elif node_status == "offline":
        connectivity_state = "offline"
    else:
        connectivity_state = "unknown"

    #
    # RPC
    #

    if rpc_healthy is True:
        rpc_state = "healthy"
    elif rpc_reachable is False:
        rpc_state = "unreachable"
    elif rpc_connected is False:
        rpc_state = "unreachable"
    elif rpc_reachable is True:
        rpc_state = "reachable"
    elif rpc_connected is True:
        # Native blockchain discovery has already successfully
        # completed an RPC observation when rpcConnected is true.
        rpc_state = "healthy"
    else:
        rpc_state = "unknown"

    #
    # Synchronization
    #

    if sync_stalled is True:
        sync_state = "stalled"

    elif sync_status in {
        "stalled",
        "sync-stalled",
    }:
        sync_state = "stalled"

    elif sync_status == "synced":
        sync_state = "synced"

    elif sync_status == "syncing":
        sync_state = "syncing"

    elif (
        sync_progress is not None
        and sync_progress >= SYNCED_THRESHOLD
    ):
        sync_state = "synced"

    elif sync_progress is not None:
        sync_state = "syncing"

    elif initial_block_download is True:
        sync_state = "syncing"

    elif initial_block_download is False:
        sync_state = "synced"

    elif (
        block_height is not None
        and header_height is not None
        and block_height > 0
        and block_height >= header_height
        and connectivity_state == "online"
    ):
        sync_state = "synced"

    else:
        sync_state = "unknown"

    #
    # Mining readiness
    #

    if (
        runtime_state in {
            "failed",
            "stopped",
            "stopping",
        }
        or connectivity_state in {
            "offline",
            "unreachable",
        }
        or rpc_state == "unreachable"
        or sync_state in {
            "syncing",
            "stalled",
        }
    ):
        mining_readiness = "not-ready"

    elif (
        sync_state == "synced"
        and connectivity_state == "online"
        and rpc_state in {
            "healthy",
            "reachable",
        }
    ):
        mining_readiness = "ready"

    else:
        mining_readiness = "unknown"

    #
    # Overall human-facing condition.
    #

    if runtime_state == "failed":
        overall_state = "failed"
        reason = "Blockchain runtime has failed."

    elif connectivity_state in {
        "offline",
        "unreachable",
    }:
        overall_state = "offline"
        reason = "Blockchain runtime is not reachable."

    elif sync_state == "stalled":
        overall_state = "stalled"
        reason = "Blockchain synchronization is stalled."

    elif sync_state == "syncing":
        overall_state = "syncing"
        reason = "Blockchain data is still synchronizing."

    elif mining_readiness == "ready":
        overall_state = "ready"
        reason = "Blockchain node is synchronized and RPC-ready."

    elif runtime_state == "running":
        overall_state = "running"
        reason = (
            "Blockchain runtime is running, but synchronization "
            "or RPC readiness is not yet known."
        )

    elif connectivity_state == "online":
        overall_state = "online"
        reason = (
            "Blockchain node is reachable, but complete runtime "
            "health is not known."
        )

    elif runtime_state in {
        "starting",
        "restarting",
        "stopping",
    }:
        overall_state = runtime_state
        reason = (
            f"Blockchain runtime is {runtime_state}."
        )

    elif runtime_state == "stopped":
        overall_state = "stopped"
        reason = "Blockchain runtime is stopped."

    else:
        overall_state = "unknown"
        reason = (
            "Nexus does not yet have enough authoritative "
            "telemetry to determine blockchain health."
        )

    return {
        "runtimeState": runtime_state,
        "connectivityState": connectivity_state,
        "syncState": sync_state,
        "rpcState": rpc_state,
        "miningReadiness": mining_readiness,
        "overallState": overall_state,
        "syncProgress": sync_progress,
        "stateReason": reason,
    }
