"""Shared Seymour MiningCore service for Nexus Platform APIs.

PostgreSQL persistence for miningcore_instances is not complete yet.
Until it is, this service uses the existing shared SMC health module
directly without making internal HTTP requests.
"""

from __future__ import annotations

from typing import Any

from backend.modules import smc_health


ONLINE_STATES = {
    "online",
    "healthy",
    "connected",
    "ready",
    "active",
    "running",
}


def _list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [
            item
            for item in value
            if isinstance(item, dict)
        ]

    return []


def _number(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _integer(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def summary() -> dict[str, Any]:
    payload = smc_health.health()

    if not isinstance(payload, dict):
        payload = {}

    instances = _list(payload.get("instances"))

    normalized = []

    for index, instance in enumerate(instances):
        status = str(
            instance.get("status")
            or "unknown"
        ).lower()

        health_score = _number(
            instance.get("healthScore")
            or instance.get("health")
        )

        api = instance.get("api")

        if not isinstance(api, dict):
            api = {}

        console = instance.get("console")

        if not isinstance(console, dict):
            console = {}

        pools = _list(instance.get("pools"))

        api_online = bool(
            api.get("online")
            or api.get("ok")
            or instance.get("apiOnline")
        )

        console_online = bool(
            console.get("online")
            or console.get("ok")
            or instance.get("consoleOnline")
        )

        online = (
            status in ONLINE_STATES
            or api_online
            or health_score >= 80
        )

        normalized.append({
            **instance,
            "instanceId": str(
                instance.get("instanceId")
                or instance.get("id")
                or instance.get("host")
                or f"miningcore-{index + 1}"
            ),
            "name": (
                instance.get("name")
                or f"Seymour MiningCore {index + 1}"
            ),
            "status": (
                "online"
                if online
                else status
            ),
            "online": online,
            "healthScore": health_score,
            "api": {
                **api,
                "online": api_online,
                "latencyMs": (
                    api.get("latencyMs")
                    or instance.get("apiLatencyMs")
                ),
            },
            "console": {
                **console,
                "online": console_online,
            },
            "pools": pools,
            "poolCount": _integer(
                instance.get("poolCount"),
                len(pools),
            ),
            "activePoolCount": _integer(
                instance.get("activePoolCount"),
                sum(
                    1
                    for pool in pools
                    if (
                        pool.get("active")
                        or str(
                            pool.get("status")
                            or ""
                        ).lower() == "active"
                    )
                ),
            ),
            "connectedMiners": _integer(
                instance.get("connectedMiners"),
                sum(
                    _integer(
                        pool.get("connectedMiners")
                        or pool.get("workerCount")
                    )
                    for pool in pools
                ),
            ),
        })

    online_count = sum(
        1
        for instance in normalized
        if instance["online"]
    )

    source_summary = payload.get("summary")

    if not isinstance(source_summary, dict):
        source_summary = {}

    return {
        "status": "ok",
        "source": "nexus-shared-miningcore-service",
        "summary": {
            **source_summary,
            "instanceCount": len(normalized),
            "onlineInstanceCount": online_count,
            "offlineInstanceCount": (
                len(normalized) - online_count
            ),
        },
        "count": len(normalized),
        "instances": normalized,
    }
