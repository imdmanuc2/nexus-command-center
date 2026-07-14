from datetime import datetime, timezone

from backend.modules import blockchain
from backend.modules import mining


def _safe_list(value):
    return value if isinstance(value, list) else []


def _safe_number(value, default=0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _node_coin(node):
    coin = (
        node.get("coin")
        or node.get("symbol")
        or node.get("blockchain")
        or node.get("chain")
        or ""
    )

    coin = str(coin).upper()

    if coin in {"BITCOIN", "BITCOIN CORE"}:
        return "BTC"

    if coin in {
        "BITCOIN CASH",
        "BITCOINCASH",
        "BITCOIN-CASH",
    }:
        return "BCH"

    return coin


def _node_status(node):
    explicit = str(
        node.get("status")
        or node.get("health")
        or ""
    ).lower()

    if explicit in {
        "online",
        "healthy",
        "connected",
        "synced",
        "ready",
    }:
        return "online"

    rpc = node.get("rpc")

    if isinstance(rpc, dict):
        if rpc.get("connected") is True:
            return "online"

        if str(rpc.get("status", "")).lower() in {
            "online",
            "connected",
            "healthy",
        }:
            return "online"

    telemetry = node.get("telemetry")

    if isinstance(telemetry, dict):
        if telemetry.get("connected") is True:
            return "online"

        if telemetry.get("networkActive") is True:
            return "online"

    if node.get("networkActive") is True:
        return "online"

    return "offline"


def _normalize_nodes(payload):
    if isinstance(payload, list):
        raw_nodes = payload
    elif isinstance(payload, dict):
        raw_nodes = (
            payload.get("nodes")
            or payload.get("blockchainNodes")
            or payload.get("items")
            or []
        )
    else:
        raw_nodes = []

    nodes = []

    for index, raw in enumerate(_safe_list(raw_nodes)):
        if not isinstance(raw, dict):
            continue

        coin = _node_coin(raw)
        status = _node_status(raw)

        telemetry = raw.get("telemetry")
        if not isinstance(telemetry, dict):
            telemetry = {}

        rpc = raw.get("rpc")
        if not isinstance(rpc, dict):
            rpc = {}

        host = (
            raw.get("host")
            or raw.get("ip")
            or telemetry.get("host")
            or rpc.get("host")
        )

        name = (
            raw.get("name")
            or raw.get("displayName")
            or raw.get("label")
            or f"{coin or 'Blockchain'} Node"
        )

        block_height = (
            raw.get("blockHeight")
            or raw.get("blocks")
            or telemetry.get("blockHeight")
            or telemetry.get("blocks")
            or rpc.get("blocks")
        )

        headers = (
            raw.get("headers")
            or telemetry.get("headers")
            or rpc.get("headers")
        )

        peers = (
            raw.get("connectedPeers")
            or raw.get("peers")
            or telemetry.get("connectedPeers")
            or telemetry.get("peers")
            or rpc.get("connections")
        )

        sync_percent = (
            raw.get("syncPercent")
            or raw.get("verificationProgress")
            or telemetry.get("syncPercent")
            or telemetry.get("verificationProgress")
            or rpc.get("verificationprogress")
        )

        if sync_percent is not None:
            sync_percent = _safe_number(sync_percent)

            if 0 <= sync_percent <= 1:
                sync_percent *= 100

        nodes.append({
            "id": (
                raw.get("id")
                or f"node-{host or index}"
            ),
            "name": name,
            "coin": coin,
            "host": host,
            "status": status,
            "online": status == "online",
            "blockHeight": block_height,
            "headers": headers,
            "peers": peers,
            "syncPercent": sync_percent,
            "networkActive": (
                raw.get("networkActive")
                if raw.get("networkActive") is not None
                else telemetry.get("networkActive")
            ),
            "version": (
                raw.get("version")
                or raw.get("subversion")
                or telemetry.get("version")
                or telemetry.get("subversion")
                or rpc.get("subversion")
            ),
            "diskBytes": (
                raw.get("diskBytes")
                or raw.get("sizeOnDisk")
                or telemetry.get("diskBytes")
                or telemetry.get("sizeOnDisk")
                or rpc.get("size_on_disk")
            ),
            "mempoolTransactions": (
                raw.get("mempoolTransactions")
                or telemetry.get("mempoolTransactions")
                or telemetry.get("mempoolSize")
                or rpc.get("mempoolTransactions")
            ),
            "raw": raw,
        })

    return nodes


def _load_nodes():
    try:
        payload = blockchain.nodes()
        return _normalize_nodes(payload), None
    except Exception as error:
        return [], str(error)


def _build_coin_operations(mining_data, nodes):
    coins = {}

    for source in _safe_list(mining_data.get("coins")):
        if not isinstance(source, dict):
            continue

        symbol = str(
            source.get("symbol")
            or "UNKNOWN"
        ).upper()

        coins[symbol] = {
            "symbol": symbol,
            "name": source.get("name") or symbol,
            "status": (
                "mining"
                if int(source.get("activePoolCount") or 0) > 0
                else "idle"
            ),
            "health": 100,
            "hashrate": _safe_number(
                source.get("hashrate")
            ),
            "sharesPerSecond": _safe_number(
                source.get("sharesPerSecond")
            ),
            "poolCount": int(
                source.get("poolCount") or 0
            ),
            "activePoolCount": int(
                source.get("activePoolCount") or 0
            ),
            "workerCount": int(
                source.get("workerCount") or 0
            ),
            "nodeCount": 0,
            "onlineNodeCount": 0,
            "nodes": [],
        }

    for node in nodes:
        symbol = str(
            node.get("coin")
            or "UNKNOWN"
        ).upper()

        coin = coins.setdefault(
            symbol,
            {
                "symbol": symbol,
                "name": symbol,
                "status": "node-online"
                if node.get("online")
                else "offline",
                "health": 100
                if node.get("online")
                else 0,
                "hashrate": 0,
                "sharesPerSecond": 0,
                "poolCount": 0,
                "activePoolCount": 0,
                "workerCount": 0,
                "nodeCount": 0,
                "onlineNodeCount": 0,
                "nodes": [],
            },
        )

        coin["nodeCount"] += 1
        coin["nodes"].append(node)

        if node.get("online"):
            coin["onlineNodeCount"] += 1

        if coin["activePoolCount"] > 0:
            coin["status"] = "mining"
        elif coin["onlineNodeCount"] > 0:
            coin["status"] = "node-online"
        else:
            coin["status"] = "offline"

        total_components = (
            coin["activePoolCount"]
            + coin["nodeCount"]
        )

        healthy_components = (
            coin["activePoolCount"]
            + coin["onlineNodeCount"]
        )

        coin["health"] = round(
            (
                healthy_components
                / total_components
                * 100
            )
            if total_components
            else 0
        )

    return sorted(
        coins.values(),
        key=lambda item: (
            item["status"] != "mining",
            item["status"] != "node-online",
            item["symbol"],
        ),
    )


def _build_top_miners(mining_data):
    workers = _safe_list(
        mining_data.get("workers")
    )

    workers = sorted(
        workers,
        key=lambda worker: _safe_number(
            worker.get("hashrate")
        ),
        reverse=True,
    )

    result = []

    for rank, worker in enumerate(
        workers[:10],
        start=1,
    ):
        result.append({
            "rank": rank,
            "workerId": worker.get("workerId"),
            "name": (
                worker.get("displayName")
                or worker.get("name")
                or worker.get("workerName")
                or "Unknown Miner"
            ),
            "fullName": worker.get("fullName"),
            "coin": worker.get("coin"),
            "poolId": worker.get("poolId"),
            "poolName": worker.get("poolName"),
            "poolHost": worker.get("poolHost"),
            "assetIp": worker.get("assetIp"),
            "hashrate": _safe_number(
                worker.get("hashrate")
            ),
            "sharesPerSecond": _safe_number(
                worker.get("sharesPerSecond")
            ),
            "status": "online",
        })

    return result


def _build_active_pools(mining_data):
    pools = (
        mining_data.get("activePools")
        or mining_data.get("pools")
        or []
    )

    active = []

    for pool in _safe_list(pools):
        if not isinstance(pool, dict):
            continue

        if pool.get("active") is False:
            continue

        active.append({
            "id": pool.get("id"),
            "nativePoolId": pool.get(
                "nativePoolId"
            ),
            "name": pool.get("name"),
            "coin": pool.get("coin"),
            "mode": pool.get("mode"),
            "visibility": pool.get(
                "visibility"
            ),
            "status": pool.get("status"),
            "host": pool.get("host"),
            "apiPort": pool.get("apiPort"),
            "stratumPorts": pool.get(
                "stratumPorts",
                [],
            ),
            "workerCount": int(
                pool.get("workerCount") or 0
            ),
            "connectedMiners": int(
                pool.get("connectedMiners") or 0
            ),
            "hashrate": _safe_number(
                pool.get("hashrate")
            ),
            "workerHashrate": _safe_number(
                pool.get("workerHashrate")
            ),
            "sharesPerSecond": _safe_number(
                pool.get("sharesPerSecond")
            ),
            "feePercent": _safe_number(
                pool.get("feePercent")
            ),
            "network": pool.get(
                "network",
                {},
            ),
        })

    active.sort(
        key=lambda pool: pool["hashrate"],
        reverse=True,
    )

    return active


def _build_alerts(
    mining_data,
    nodes,
    node_error,
):
    alerts = []

    for error in _safe_list(
        mining_data.get("errors")
    ):
        if not isinstance(error, dict):
            continue

        alerts.append({
            "severity": "warning",
            "type": "miningcore",
            "title": "MiningCore connection issue",
            "message": error.get("error")
            or "MiningCore instance unavailable",
            "source": error.get("instanceName")
            or error.get("endpoint"),
        })

    if node_error:
        alerts.append({
            "severity": "warning",
            "type": "blockchain",
            "title": "Node telemetry unavailable",
            "message": node_error,
            "source": "Blockchain module",
        })

    for node in nodes:
        if not node.get("online"):
            alerts.append({
                "severity": "critical",
                "type": "blockchain-node",
                "title": "Blockchain node offline",
                "message": (
                    f"{node.get('name')} is offline"
                ),
                "source": node.get("host"),
            })

    return alerts


def home():
    mining_data = mining.summary()
    nodes, node_error = _load_nodes()

    active_pools = _build_active_pools(
        mining_data
    )

    top_miners = _build_top_miners(
        mining_data
    )

    coins = _build_coin_operations(
        mining_data,
        nodes,
    )

    alerts = _build_alerts(
        mining_data,
        nodes,
        node_error,
    )

    online_nodes = sum(
        1
        for node in nodes
        if node.get("online")
    )

    online_workers = len(
        _safe_list(mining_data.get("workers"))
    )

    critical_count = sum(
        1
        for alert in alerts
        if alert.get("severity") == "critical"
    )

    warning_count = sum(
        1
        for alert in alerts
        if alert.get("severity") == "warning"
    )

    total_components = (
        int(
            mining_data.get("activePoolCount")
            or 0
        )
        + len(nodes)
        + online_workers
    )

    healthy_components = (
        int(
            mining_data.get("activePoolCount")
            or 0
        )
        + online_nodes
        + online_workers
    )

    fleet_health = round(
        (
            healthy_components
            / total_components
            * 100
        )
        if total_components
        else 0
    )

    if critical_count:
        status = "critical"
    elif warning_count:
        status = "warning"
    elif (
        mining_data.get("status")
        in {"online", "partial"}
    ):
        status = "online"
    else:
        status = "offline"

    return {
        "generatedAt": datetime.now(
            timezone.utc
        ).isoformat(),
        "status": status,
        "summary": {
            "fleetHashrate": _safe_number(
                mining_data.get(
                    "totalHashrate"
                )
            ),
            "sharesPerSecond": _safe_number(
                mining_data.get(
                    "sharesPerSecond"
                )
            ),
            "coinCount": len(coins),
            "poolCount": int(
                mining_data.get("poolCount")
                or 0
            ),
            "activePoolCount": int(
                mining_data.get(
                    "activePoolCount"
                )
                or 0
            ),
            "minerCount": int(
                mining_data.get("workerCount")
                or online_workers
            ),
            "onlineMinerCount": online_workers,
            "nodeCount": len(nodes),
            "onlineNodeCount": online_nodes,
            "fleetHealth": fleet_health,
            "warningCount": warning_count,
            "criticalCount": critical_count,
        },
        "coins": coins,
        "activePools": active_pools,
        "topMiners": top_miners,
        "nodes": nodes,
        "alerts": alerts,
        "activity": [],
        "dataSources": {
            "mining": mining_data.get(
                "status"
            ),
            "blockchain": (
                "error"
                if node_error
                else "online"
            ),
        },
    }
