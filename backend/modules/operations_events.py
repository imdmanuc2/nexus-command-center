import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from backend.modules import fleet
from backend.modules import smc_health


DATA_DIR = Path("backend/data/events")
STATE_PATH = DATA_DIR / "operations-state.json"
EVENTS_PATH = DATA_DIR / "operations-events.json"

MAX_EVENTS = 500

_LOCK = threading.Lock()


def _now():
    return datetime.now(timezone.utc).isoformat()


def _number(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _integer(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _load_json(path, default):
    try:
        if not path.exists():
            return default

        return json.loads(path.read_text())
    except Exception:
        return default


def _save_json(path, payload):
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    temporary = path.with_suffix(
        path.suffix + ".tmp"
    )

    temporary.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
        )
    )

    temporary.replace(path)


def _event_id(timestamp, event_type, object_id):
    compact_time = (
        timestamp
        .replace("-", "")
        .replace(":", "")
        .replace(".", "")
        .replace("+", "")
    )

    return (
        f"evt-{compact_time}-"
        f"{event_type}-"
        f"{str(object_id).replace(' ', '-')}"
    )


def _make_event(
    event_type,
    severity,
    title,
    message,
    source,
    object_type=None,
    object_id=None,
    metadata=None,
):
    timestamp = _now()

    return {
        "id": _event_id(
            timestamp,
            event_type,
            object_id or source or "nexus",
        ),
        "timestamp": timestamp,
        "type": event_type,
        "severity": severity,
        "title": title,
        "message": message,
        "source": source,
        "objectType": object_type,
        "objectId": object_id,
        "metadata": metadata or {},
    }


def _normalize_fleet_state(payload):
    summary = payload.get("summary") or {}

    nodes = {}

    for node in payload.get("nodes") or []:
        node_id = str(
            node.get("id")
            or node.get("host")
            or node.get("name")
        )

        nodes[node_id] = {
            "id": node_id,
            "name": node.get("name"),
            "host": node.get("host"),
            "coin": node.get("coin"),
            "online": bool(node.get("online")),
            "blockHeight": _integer(
                node.get("blockHeight")
            ),
            "peers": _integer(
                node.get("peers")
            ),
            "syncPercent": _number(
                node.get("syncPercent")
            ),
        }

    pools = {}

    for pool in payload.get("activePools") or []:
        pool_id = str(
            pool.get("id")
            or pool.get("name")
        )

        pools[pool_id] = {
            "id": pool_id,
            "name": pool.get("name"),
            "host": pool.get("host"),
            "status": pool.get("status"),
            "active": (
                pool.get("status") == "active"
                or bool(
                    pool.get("workerCount")
                    or pool.get("hashrate")
                )
            ),
            "workerCount": _integer(
                pool.get("workerCount")
            ),
            "hashrate": _number(
                pool.get("hashrate")
            ),
        }

    miners = {}

    for miner in payload.get("topMiners") or []:
        miner_id = str(
            miner.get("workerId")
            or miner.get("name")
        )

        miners[miner_id] = {
            "id": miner_id,
            "name": miner.get("name"),
            "poolName": miner.get("poolName"),
            "poolHost": miner.get("poolHost"),
            "hashrate": _number(
                miner.get("hashrate")
            ),
            "online": (
                str(
                    miner.get("status")
                    or "online"
                ).lower()
                != "offline"
            ),
        }

    alerts = {}

    for alert in payload.get("alerts") or []:
        alert_id = "|".join([
            str(alert.get("severity") or ""),
            str(alert.get("title") or ""),
            str(alert.get("source") or ""),
        ])

        alerts[alert_id] = {
            "id": alert_id,
            "severity": alert.get("severity"),
            "title": alert.get("title"),
            "message": alert.get("message"),
            "source": alert.get("source"),
        }

    return {
        "summary": {
            "fleetHashrate": _number(
                summary.get("fleetHashrate")
            ),
            "onlineMinerCount": _integer(
                summary.get("onlineMinerCount")
            ),
            "activePoolCount": _integer(
                summary.get("activePoolCount")
            ),
            "onlineNodeCount": _integer(
                summary.get("onlineNodeCount")
            ),
            "warningCount": _integer(
                summary.get("warningCount")
            ),
            "criticalCount": _integer(
                summary.get("criticalCount")
            ),
        },
        "nodes": nodes,
        "pools": pools,
        "miners": miners,
        "alerts": alerts,
    }


def _normalize_smc_state(payload):
    instances = {}

    for instance in payload.get("instances") or []:
        instance_id = str(
            instance.get("id")
            or instance.get("host")
            or instance.get("name")
        )

        pools = {}

        for pool in instance.get("pools") or []:
            pool_id = str(
                pool.get("id")
                or pool.get("name")
            )

            pools[pool_id] = {
                "id": pool_id,
                "name": pool.get("name"),
                "active": bool(pool.get("active")),
                "connectedMiners": _integer(
                    pool.get("connectedMiners")
                ),
                "hashrate": _number(
                    pool.get("hashrate")
                ),
                "stratumHealthy": bool(
                    pool.get("stratumHealthy")
                ),
            }

        instances[instance_id] = {
            "id": instance_id,
            "name": instance.get("name"),
            "host": instance.get("host"),
            "status": instance.get("status"),
            "healthScore": _integer(
                instance.get("healthScore")
            ),
            "apiOnline": bool(
                instance.get("api", {}).get("online")
            ),
            "consoleOnline": bool(
                instance.get(
                    "console",
                    {},
                ).get("online")
            ),
            "pools": pools,
        }

    return {
        "instances": instances,
    }


def _percent_change(previous, current):
    previous = _number(previous)
    current = _number(current)

    if previous <= 0:
        return 0

    return (
        (current - previous)
        / previous
        * 100
    )


def _compare_nodes(previous, current):
    events = []

    old_nodes = previous.get("nodes") or {}
    new_nodes = current.get("nodes") or {}

    for node_id, node in new_nodes.items():
        old = old_nodes.get(node_id)

        if old is None:
            events.append(
                _make_event(
                    "node-discovered",
                    "info",
                    "Blockchain node discovered",
                    (
                        f"{node.get('name')} is now "
                        "being monitored by Nexus."
                    ),
                    node.get("host"),
                    "blockchain-node",
                    node_id,
                    node,
                )
            )
            continue

        if old.get("online") != node.get("online"):
            online = node.get("online")

            events.append(
                _make_event(
                    (
                        "node-online"
                        if online
                        else "node-offline"
                    ),
                    (
                        "recovery"
                        if online
                        else "critical"
                    ),
                    (
                        "Blockchain node restored"
                        if online
                        else "Blockchain node offline"
                    ),
                    (
                        f"{node.get('name')} is "
                        f"{'online again' if online else 'not responding'}."
                    ),
                    node.get("host"),
                    "blockchain-node",
                    node_id,
                    node,
                )
            )

        old_height = _integer(
            old.get("blockHeight")
        )

        new_height = _integer(
            node.get("blockHeight")
        )

        if (
            new_height > 0
            and new_height > old_height
        ):
            events.append(
                _make_event(
                    "new-block",
                    "info",
                    "New blockchain block observed",
                    (
                        f"{node.get('name')} advanced "
                        f"from block {old_height:,} "
                        f"to {new_height:,}."
                    ),
                    node.get("host"),
                    "blockchain-node",
                    node_id,
                    {
                        "previousBlockHeight": old_height,
                        "blockHeight": new_height,
                        "coin": node.get("coin"),
                    },
                )
            )

        old_peers = _integer(
            old.get("peers")
        )

        new_peers = _integer(
            node.get("peers")
        )

        if (
            old_peers != new_peers
            and new_peers >= 0
        ):
            severity = (
                "warning"
                if new_peers < 4
                else "info"
            )

            events.append(
                _make_event(
                    "peer-count-changed",
                    severity,
                    "Blockchain peer count changed",
                    (
                        f"{node.get('name')} peers "
                        f"changed from {old_peers} "
                        f"to {new_peers}."
                    ),
                    node.get("host"),
                    "blockchain-node",
                    node_id,
                    {
                        "previousPeers": old_peers,
                        "peers": new_peers,
                    },
                )
            )

    for node_id, node in old_nodes.items():
        if node_id not in new_nodes:
            events.append(
                _make_event(
                    "node-missing",
                    "critical",
                    "Blockchain node disappeared",
                    (
                        f"{node.get('name')} is no "
                        "longer present in Fleet telemetry."
                    ),
                    node.get("host"),
                    "blockchain-node",
                    node_id,
                    node,
                )
            )

    return events


def _compare_pools(previous, current):
    events = []

    old_pools = previous.get("pools") or {}
    new_pools = current.get("pools") or {}

    for pool_id, pool in new_pools.items():
        old = old_pools.get(pool_id)

        if old is None:
            events.append(
                _make_event(
                    "pool-discovered",
                    "info",
                    "Mining pool discovered",
                    (
                        f"{pool.get('name')} is now "
                        "being monitored."
                    ),
                    pool.get("host"),
                    "mining-pool",
                    pool_id,
                    pool,
                )
            )
            continue

        if old.get("active") != pool.get("active"):
            active = pool.get("active")

            events.append(
                _make_event(
                    (
                        "pool-active"
                        if active
                        else "pool-idle"
                    ),
                    (
                        "recovery"
                        if active
                        else "warning"
                    ),
                    (
                        "Mining pool active"
                        if active
                        else "Mining pool became idle"
                    ),
                    (
                        f"{pool.get('name')} is now "
                        f"{'active' if active else 'idle'}."
                    ),
                    pool.get("host"),
                    "mining-pool",
                    pool_id,
                    pool,
                )
            )

        old_workers = _integer(
            old.get("workerCount")
        )

        new_workers = _integer(
            pool.get("workerCount")
        )

        if old_workers != new_workers:
            severity = (
                "warning"
                if new_workers < old_workers
                else "info"
            )

            events.append(
                _make_event(
                    "pool-worker-count-changed",
                    severity,
                    "Pool miner count changed",
                    (
                        f"{pool.get('name')} miners "
                        f"changed from {old_workers} "
                        f"to {new_workers}."
                    ),
                    pool.get("host"),
                    "mining-pool",
                    pool_id,
                    {
                        "previousWorkerCount": old_workers,
                        "workerCount": new_workers,
                    },
                )
            )

        change = _percent_change(
            old.get("hashrate"),
            pool.get("hashrate"),
        )

        if abs(change) >= 20:
            severity = (
                "warning"
                if change < 0
                else "info"
            )

            events.append(
                _make_event(
                    "pool-hashrate-shift",
                    severity,
                    "Pool hashrate changed significantly",
                    (
                        f"{pool.get('name')} hashrate "
                        f"{'fell' if change < 0 else 'increased'} "
                        f"{abs(change):.1f}%."
                    ),
                    pool.get("host"),
                    "mining-pool",
                    pool_id,
                    {
                        "changePercent": round(
                            change,
                            2,
                        ),
                        "previousHashrate": old.get(
                            "hashrate"
                        ),
                        "hashrate": pool.get(
                            "hashrate"
                        ),
                    },
                )
            )

    for pool_id, pool in old_pools.items():
        if pool_id not in new_pools:
            events.append(
                _make_event(
                    "pool-missing",
                    "critical",
                    "Mining pool disappeared",
                    (
                        f"{pool.get('name')} is no "
                        "longer present in Fleet telemetry."
                    ),
                    pool.get("host"),
                    "mining-pool",
                    pool_id,
                    pool,
                )
            )

    return events


def _compare_miners(previous, current):
    events = []

    old_miners = previous.get("miners") or {}
    new_miners = current.get("miners") or {}

    for miner_id, miner in new_miners.items():
        old = old_miners.get(miner_id)

        if old is None:
            events.append(
                _make_event(
                    "miner-online",
                    "recovery",
                    "Miner connected",
                    (
                        f"{miner.get('name')} appeared "
                        f"on {miner.get('poolName')}."
                    ),
                    miner.get("poolHost"),
                    "miner",
                    miner_id,
                    miner,
                )
            )
            continue

        change = _percent_change(
            old.get("hashrate"),
            miner.get("hashrate"),
        )

        if abs(change) >= 25:
            events.append(
                _make_event(
                    "miner-hashrate-shift",
                    (
                        "warning"
                        if change < 0
                        else "info"
                    ),
                    "Miner hashrate changed significantly",
                    (
                        f"{miner.get('name')} hashrate "
                        f"{'fell' if change < 0 else 'increased'} "
                        f"{abs(change):.1f}%."
                    ),
                    miner.get("poolHost"),
                    "miner",
                    miner_id,
                    {
                        "changePercent": round(
                            change,
                            2,
                        ),
                        "previousHashrate": old.get(
                            "hashrate"
                        ),
                        "hashrate": miner.get(
                            "hashrate"
                        ),
                    },
                )
            )

    for miner_id, miner in old_miners.items():
        if miner_id not in new_miners:
            events.append(
                _make_event(
                    "miner-offline",
                    "critical",
                    "Miner disconnected",
                    (
                        f"{miner.get('name')} disappeared "
                        f"from {miner.get('poolName')}."
                    ),
                    miner.get("poolHost"),
                    "miner",
                    miner_id,
                    miner,
                )
            )

    return events


def _compare_alerts(previous, current):
    events = []

    old_alerts = previous.get("alerts") or {}
    new_alerts = current.get("alerts") or {}

    for alert_id, alert in new_alerts.items():
        if alert_id in old_alerts:
            continue

        severity = str(
            alert.get("severity")
            or "warning"
        ).lower()

        events.append(
            _make_event(
                "alert-opened",
                severity,
                alert.get("title")
                or "Operations alert opened",
                alert.get("message")
                or "A new fleet alert was detected.",
                alert.get("source")
                or "Nexus",
                "alert",
                alert_id,
                alert,
            )
        )

    for alert_id, alert in old_alerts.items():
        if alert_id in new_alerts:
            continue

        events.append(
            _make_event(
                "alert-resolved",
                "recovery",
                "Operations alert resolved",
                (
                    f"{alert.get('title')} is no "
                    "longer active."
                ),
                alert.get("source")
                or "Nexus",
                "alert",
                alert_id,
                alert,
            )
        )

    return events


def _compare_smc(previous, current):
    events = []

    old_instances = previous.get("instances") or {}
    new_instances = current.get("instances") or {}

    for instance_id, instance in new_instances.items():
        old = old_instances.get(instance_id)

        if old is None:
            events.append(
                _make_event(
                    "smc-discovered",
                    "info",
                    "Seymour MiningCore discovered",
                    (
                        f"{instance.get('name')} is now "
                        "being monitored."
                    ),
                    instance.get("host"),
                    "smc-instance",
                    instance_id,
                    instance,
                )
            )
            continue

        for field, label in [
            ("apiOnline", "API"),
            ("consoleOnline", "console"),
        ]:
            if old.get(field) == instance.get(field):
                continue

            online = instance.get(field)

            events.append(
                _make_event(
                    (
                        f"smc-{label.lower()}-restored"
                        if online
                        else f"smc-{label.lower()}-offline"
                    ),
                    (
                        "recovery"
                        if online
                        else "critical"
                    ),
                    (
                        f"Seymour MiningCore {label} restored"
                        if online
                        else f"Seymour MiningCore {label} offline"
                    ),
                    (
                        f"{instance.get('name')} {label} "
                        f"is {'online again' if online else 'unavailable'}."
                    ),
                    instance.get("host"),
                    "smc-instance",
                    instance_id,
                    {
                        "component": label.lower(),
                        "online": online,
                    },
                )
            )

        old_score = _integer(
            old.get("healthScore")
        )

        new_score = _integer(
            instance.get("healthScore")
        )

        if (
            old_score != new_score
            and abs(new_score - old_score) >= 10
        ):
            events.append(
                _make_event(
                    "smc-health-changed",
                    (
                        "warning"
                        if new_score < old_score
                        else "recovery"
                    ),
                    "Seymour MiningCore health changed",
                    (
                        f"{instance.get('name')} health "
                        f"changed from {old_score}% "
                        f"to {new_score}%."
                    ),
                    instance.get("host"),
                    "smc-instance",
                    instance_id,
                    {
                        "previousHealthScore": old_score,
                        "healthScore": new_score,
                    },
                )
            )

        old_pools = old.get("pools") or {}
        new_pools = instance.get("pools") or {}

        for pool_id, pool in new_pools.items():
            old_pool = old_pools.get(pool_id)

            if old_pool is None:
                continue

            if (
                old_pool.get("stratumHealthy")
                != pool.get("stratumHealthy")
            ):
                healthy = pool.get(
                    "stratumHealthy"
                )

                events.append(
                    _make_event(
                        (
                            "stratum-restored"
                            if healthy
                            else "stratum-offline"
                        ),
                        (
                            "recovery"
                            if healthy
                            else "critical"
                        ),
                        (
                            "Stratum restored"
                            if healthy
                            else "Stratum unavailable"
                        ),
                        (
                            f"{pool.get('name')} Stratum "
                            f"is {'healthy again' if healthy else 'not accepting connections'}."
                        ),
                        instance.get("host"),
                        "mining-pool",
                        pool_id,
                        pool,
                    )
                )

    for instance_id, instance in old_instances.items():
        if instance_id not in new_instances:
            events.append(
                _make_event(
                    "smc-missing",
                    "critical",
                    "Seymour MiningCore disappeared",
                    (
                        f"{instance.get('name')} is no "
                        "longer present in health telemetry."
                    ),
                    instance.get("host"),
                    "smc-instance",
                    instance_id,
                    instance,
                )
            )

    return events


def _initial_events(fleet_state, smc_state):
    return [
        _make_event(
            "monitoring-started",
            "info",
            "Operations monitoring initialized",
            (
                "Nexus established the initial "
                "fleet and Seymour MiningCore baseline."
            ),
            "Nexus Command Center",
            "system",
            "nexus",
            {
                "nodes": len(
                    fleet_state.get("nodes") or {}
                ),
                "pools": len(
                    fleet_state.get("pools") or {}
                ),
                "miners": len(
                    fleet_state.get("miners") or {}
                ),
                "smcInstances": len(
                    smc_state.get("instances") or {}
                ),
            },
        )
    ]


def _collect():
    fleet_payload = fleet.home()
    smc_payload = smc_health.health()

    fleet_state = _normalize_fleet_state(
        fleet_payload
    )

    smc_state = _normalize_smc_state(
        smc_payload
    )

    previous = _load_json(
        STATE_PATH,
        {},
    )

    previous_fleet = (
        previous.get("fleet")
        or {}
    )

    previous_smc = (
        previous.get("smc")
        or {}
    )

    if not previous:
        new_events = _initial_events(
            fleet_state,
            smc_state,
        )
    else:
        new_events = []

        new_events.extend(
            _compare_nodes(
                previous_fleet,
                fleet_state,
            )
        )

        new_events.extend(
            _compare_pools(
                previous_fleet,
                fleet_state,
            )
        )

        new_events.extend(
            _compare_miners(
                previous_fleet,
                fleet_state,
            )
        )

        new_events.extend(
            _compare_alerts(
                previous_fleet,
                fleet_state,
            )
        )

        new_events.extend(
            _compare_smc(
                previous_smc,
                smc_state,
            )
        )

    stored_events = _load_json(
        EVENTS_PATH,
        [],
    )

    if not isinstance(stored_events, list):
        stored_events = []

    if new_events:
        stored_events = (
            new_events
            + stored_events
        )[:MAX_EVENTS]

        _save_json(
            EVENTS_PATH,
            stored_events,
        )

    _save_json(
        STATE_PATH,
        {
            "updatedAt": _now(),
            "fleet": fleet_state,
            "smc": smc_state,
        },
    )

    return stored_events, new_events


def events(limit=100):
    with _LOCK:
        stored_events, new_events = _collect()

    limit = max(
        1,
        min(
            _integer(limit, 100),
            MAX_EVENTS,
        ),
    )

    items = stored_events[:limit]

    counts = {
        "critical": 0,
        "warning": 0,
        "recovery": 0,
        "info": 0,
    }

    for item in items:
        severity = str(
            item.get("severity")
            or "info"
        ).lower()

        if severity not in counts:
            severity = "info"

        counts[severity] += 1

    return {
        "generatedAt": _now(),
        "count": len(items),
        "newEventCount": len(new_events),
        "counts": counts,
        "events": items,
    }


def clear():
    with _LOCK:
        _save_json(
            EVENTS_PATH,
            [],
        )

    return {
        "success": True,
        "message": "Operations event history cleared.",
    }
