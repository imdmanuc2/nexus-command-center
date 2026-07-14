import json
import socket
import time
from datetime import datetime, timezone
from urllib.parse import urlparse
from urllib.request import Request, urlopen


SMC_INSTANCES = [
    {
        "id": "smc-192-168-1-154",
        "name": "Seymour MiningCore .154",
        "host": "192.168.1.154",
        "apiBase": "http://192.168.1.154:4000",
        "consolePort": 8559,
    },
    {
        "id": "smc-192-168-1-156",
        "name": "Seymour MiningCore .156",
        "host": "192.168.1.156",
        "apiBase": "http://192.168.1.156:4000",
        "consolePort": 8559,
    },
]


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


def _fetch_json(url, timeout=5):
    started = time.perf_counter()

    request = Request(
        url,
        headers={
            "User-Agent": "Nexus-Seymour-MiningCore-Health/1.0",
            "Accept": "application/json",
        },
    )

    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(
            response.read().decode(
                "utf-8",
                errors="ignore",
            )
        )

        latency_ms = round(
            (time.perf_counter() - started) * 1000,
            2,
        )

        return {
            "ok": True,
            "statusCode": response.status,
            "latencyMs": latency_ms,
            "payload": payload,
            "error": None,
        }


def _fetch_json_safe(url, timeout=5):
    try:
        return _fetch_json(url, timeout)
    except Exception as error:
        return {
            "ok": False,
            "statusCode": None,
            "latencyMs": None,
            "payload": None,
            "error": str(error),
        }


def _tcp_check(host, port, timeout=2):
    started = time.perf_counter()

    try:
        with socket.create_connection(
            (host, int(port)),
            timeout=timeout,
        ):
            latency_ms = round(
                (time.perf_counter() - started) * 1000,
                2,
            )

            return {
                "port": int(port),
                "open": True,
                "latencyMs": latency_ms,
                "error": None,
            }

    except Exception as error:
        return {
            "port": int(port),
            "open": False,
            "latencyMs": None,
            "error": str(error),
        }


def _pool_details(instance, discovered_pool):
    api_base = instance["apiBase"].rstrip("/")
    native_pool_id = str(
        discovered_pool.get("id")
        or "unknown"
    )

    detail_result = _fetch_json_safe(
        f"{api_base}/api/pools/{native_pool_id}"
    )

    if detail_result["ok"]:
        pool = (
            detail_result["payload"].get("pool")
            or discovered_pool
        )
    else:
        pool = discovered_pool

    coin = pool.get("coin") or {}
    pool_stats = pool.get("poolStats") or {}
    network_stats = pool.get("networkStats") or {}
    ports = pool.get("ports") or {}

    stratum_checks = []

    for port in ports.keys():
        stratum_checks.append(
            _tcp_check(
                instance["host"],
                int(port),
            )
        )

    connected_miners = _integer(
        pool_stats.get("connectedMiners")
    )

    hashrate = _number(
        pool_stats.get("poolHashrate")
    )

    shares_per_second = _number(
        pool_stats.get("sharesPerSecond")
    )

    active = (
        connected_miners > 0
        or hashrate > 0
        or shares_per_second > 0
    )

    return {
        "id": (
            f"{instance['id']}-"
            f"{native_pool_id}"
        ),
        "nativePoolId": native_pool_id,
        "name": (
            f"{coin.get('symbol') or native_pool_id.upper()} "
            f"{'Solo' if str(pool.get('paymentProcessing', {}).get('payoutScheme')).upper() == 'SOLO' else 'Public'} "
            f"· {instance['host']}"
        ),
        "coin": {
            "symbol": (
                coin.get("symbol")
                or coin.get("type")
                or native_pool_id.upper()
            ),
            "name": (
                coin.get("name")
                or native_pool_id.upper()
            ),
        },
        "active": active,
        "mode": (
            "solo"
            if str(
                pool.get(
                    "paymentProcessing",
                    {},
                ).get("payoutScheme")
            ).upper() == "SOLO"
            else "public"
        ),
        "visibility": (
            "private"
            if str(
                pool.get(
                    "paymentProcessing",
                    {},
                ).get("payoutScheme")
            ).upper() == "SOLO"
            else "public"
        ),
        "connectedMiners": connected_miners,
        "hashrate": hashrate,
        "sharesPerSecond": shares_per_second,
        "feePercent": _number(
            pool.get("poolFeePercent")
        ),
        "stratumPorts": [
            int(port)
            for port in ports.keys()
        ],
        "stratumChecks": stratum_checks,
        "stratumHealthy": (
            bool(stratum_checks)
            and all(
                check["open"]
                for check in stratum_checks
            )
        ),
        "network": {
            "blockHeight": network_stats.get(
                "blockHeight"
            ),
            "connectedPeers": network_stats.get(
                "connectedPeers"
            ),
            "networkDifficulty": network_stats.get(
                "networkDifficulty"
            ),
            "networkHashrate": network_stats.get(
                "networkHashrate"
            ),
            "nodeVersion": network_stats.get(
                "nodeVersion"
            ),
            "lastNetworkBlockTime": network_stats.get(
                "lastNetworkBlockTime"
            ),
        },
        "api": {
            "ok": detail_result["ok"],
            "latencyMs": detail_result["latencyMs"],
            "error": detail_result["error"],
        },
    }


def _health_score(
    api_online,
    console_online,
    pools,
):
    score = 100
    findings = []

    if not api_online:
        score -= 60
        findings.append({
            "severity": "critical",
            "component": "api",
            "message": "MiningCore API is unavailable.",
        })

    if not console_online:
        score -= 10
        findings.append({
            "severity": "warning",
            "component": "console",
            "message": (
                "Seymour MiningCore local console "
                "is not reachable on port 8559."
            ),
        })

    if api_online and not pools:
        score -= 20
        findings.append({
            "severity": "warning",
            "component": "pools",
            "message": (
                "MiningCore API is online but "
                "reported no configured pools."
            ),
        })

    for pool in pools:
        if not pool["api"]["ok"]:
            score -= 20
            findings.append({
                "severity": "critical",
                "component": "pool-api",
                "poolId": pool["id"],
                "message": (
                    f"{pool['name']} API detail "
                    "could not be loaded."
                ),
            })

        if (
            pool["stratumPorts"]
            and not pool["stratumHealthy"]
        ):
            score -= 25
            findings.append({
                "severity": "critical",
                "component": "stratum",
                "poolId": pool["id"],
                "message": (
                    f"One or more Stratum ports for "
                    f"{pool['name']} are unavailable."
                ),
            })

        if (
            pool["active"]
            and pool["connectedMiners"] == 0
        ):
            score -= 10
            findings.append({
                "severity": "warning",
                "component": "miners",
                "poolId": pool["id"],
                "message": (
                    f"{pool['name']} has activity "
                    "but reports zero connected miners."
                ),
            })

    score = max(0, min(100, score))

    if score >= 90:
        level = "healthy"
    elif score >= 70:
        level = "warning"
    else:
        level = "critical"

    return {
        "score": score,
        "level": level,
        "findings": findings,
    }


def _instance_health(instance):
    api_base = instance["apiBase"].rstrip("/")

    pools_result = _fetch_json_safe(
        f"{api_base}/api/pools"
    )

    api_online = pools_result["ok"]

    console_check = _tcp_check(
        instance["host"],
        instance["consolePort"],
    )

    discovered_pools = []

    if api_online:
        discovered_pools = (
            pools_result["payload"].get("pools")
            or []
        )

    pools = []

    for discovered_pool in discovered_pools:
        if not isinstance(discovered_pool, dict):
            continue

        pools.append(
            _pool_details(
                instance,
                discovered_pool,
            )
        )

    health = _health_score(
        api_online,
        console_check["open"],
        pools,
    )

    active_pools = [
        pool
        for pool in pools
        if pool["active"]
    ]

    return {
        "id": instance["id"],
        "name": instance["name"],
        "host": instance["host"],
        "apiBase": api_base,
        "status": health["level"],
        "healthScore": health["score"],
        "api": {
            "online": api_online,
            "latencyMs": pools_result["latencyMs"],
            "statusCode": pools_result["statusCode"],
            "error": pools_result["error"],
        },
        "console": {
            "port": instance["consolePort"],
            "online": console_check["open"],
            "latencyMs": console_check["latencyMs"],
            "error": console_check["error"],
        },
        "poolCount": len(pools),
        "activePoolCount": len(active_pools),
        "connectedMiners": sum(
            pool["connectedMiners"]
            for pool in pools
        ),
        "totalHashrate": sum(
            pool["hashrate"]
            for pool in active_pools
        ),
        "sharesPerSecond": sum(
            pool["sharesPerSecond"]
            for pool in active_pools
        ),
        "pools": pools,
        "findings": health["findings"],
    }


def health():
    instances = [
        _instance_health(instance)
        for instance in SMC_INSTANCES
    ]

    instance_count = len(instances)

    online_instances = sum(
        1
        for instance in instances
        if instance["api"]["online"]
    )

    healthy_instances = sum(
        1
        for instance in instances
        if instance["status"] == "healthy"
    )

    warning_count = sum(
        1
        for instance in instances
        for finding in instance["findings"]
        if finding["severity"] == "warning"
    )

    critical_count = sum(
        1
        for instance in instances
        for finding in instance["findings"]
        if finding["severity"] == "critical"
    )

    average_health = round(
        sum(
            instance["healthScore"]
            for instance in instances
        ) / instance_count
    ) if instance_count else 0

    if critical_count:
        status = "critical"
    elif warning_count:
        status = "warning"
    elif online_instances == instance_count:
        status = "healthy"
    else:
        status = "offline"

    return {
        "generatedAt": _now(),
        "status": status,
        "summary": {
            "instanceCount": instance_count,
            "onlineInstanceCount": online_instances,
            "healthyInstanceCount": healthy_instances,
            "healthScore": average_health,
            "poolCount": sum(
                instance["poolCount"]
                for instance in instances
            ),
            "activePoolCount": sum(
                instance["activePoolCount"]
                for instance in instances
            ),
            "connectedMiners": sum(
                instance["connectedMiners"]
                for instance in instances
            ),
            "totalHashrate": sum(
                instance["totalHashrate"]
                for instance in instances
            ),
            "sharesPerSecond": sum(
                instance["sharesPerSecond"]
                for instance in instances
            ),
            "warningCount": warning_count,
            "criticalCount": critical_count,
        },
        "instances": instances,
    }
