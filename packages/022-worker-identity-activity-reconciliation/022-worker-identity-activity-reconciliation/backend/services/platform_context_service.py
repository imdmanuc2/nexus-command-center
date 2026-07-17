from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.db.repositories.alert_repository import (
    alert_summary,
    list_alerts,
)
from backend.db.repositories.asset_repository import list_assets
from backend.db.repositories.blockchain_repository import (
    list_blockchain_nodes,
)
from backend.db.repositories.context_repository import (
    get_context,
    upsert_context,
    update_builder_state,
)
from backend.db.repositories.miningcore_repository import (
    list_miningcore_instances,
)
from backend.db.repositories.platform_event_repository import (
    event_summary,
    list_events,
)
from backend.db.repositories.pool_repository import list_pools
from backend.db.repositories.telemetry_repository import (
    list_current_metrics,
    telemetry_summary,
)
from backend.db.repositories.worker_repository import list_active_workers
from backend.db.repositories.workload_repository import list_workloads


def _status_count(records: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}

    for record in records:
        status = str(record.get("status") or "unknown").lower()
        counts[status] = counts.get(status, 0) + 1

    return counts


def _active_alerts(
    alerts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return [
        alert
        for alert in alerts
        if alert.get("status") in {"open", "acknowledged"}
    ]


def _metric_lookup(
    metrics: list[dict[str, Any]],
) -> dict[str, dict[str, dict[str, Any]]]:
    lookup: dict[str, dict[str, dict[str, Any]]] = {}

    for metric in metrics:
        entity_key = (
            f"{metric.get('entityType')}:{metric.get('entityId')}"
        )
        lookup.setdefault(entity_key, {})[
            str(metric.get("metricName"))
        ] = metric

    return lookup


def _health_score(
    *,
    workers: list[dict[str, Any]],
    pools: list[dict[str, Any]],
    nodes: list[dict[str, Any]],
    miningcore: list[dict[str, Any]],
    active_alerts: list[dict[str, Any]],
) -> float:
    resources = [
        *workers,
        *pools,
        *nodes,
        *miningcore,
    ]

    if not resources:
        return 100.0

    unhealthy = 0

    for resource in resources:
        status = str(resource.get("status") or "unknown").lower()
        if status in {"offline", "down", "error", "failed"}:
            unhealthy += 1
        elif status in {"warning", "degraded", "stale"}:
            unhealthy += 0.5

    critical_alerts = sum(
        1
        for alert in active_alerts
        if alert.get("severity") == "critical"
    )
    warning_alerts = sum(
        1
        for alert in active_alerts
        if alert.get("severity") == "warning"
    )

    penalty = (
        (unhealthy / len(resources)) * 100
        + critical_alerts * 10
        + warning_alerts * 4
    )

    return round(max(0.0, min(100.0, 100.0 - penalty)), 2)


def build_contexts() -> dict[str, Any]:
    started = datetime.now(timezone.utc)

    update_builder_state(
        status="running",
        started_at=started,
    )

    try:
        assets = list_assets()
        workers = list_active_workers()
        pools = list_pools()
        workloads = list_workloads()
        nodes = list_blockchain_nodes()
        miningcore = list_miningcore_instances()
        metrics = list_current_metrics(limit=5000)
        alerts = list_alerts(limit=250)
        events = list_events(limit=100)

        active_alerts = _active_alerts(alerts)
        metric_lookup = _metric_lookup(metrics)

        health_score = _health_score(
            workers=workers,
            pools=pools,
            nodes=nodes,
            miningcore=miningcore,
            active_alerts=active_alerts,
        )

        source_state = {
            "assets": len(assets),
            "workers": len(workers),
            "pools": len(pools),
            "workloads": len(workloads),
            "nodes": len(nodes),
            "miningcoreInstances": len(miningcore),
            "currentMetrics": len(metrics),
            "alerts": len(alerts),
            "events": len(events),
        }

        overview = {
            "generatedAt": started.isoformat(),
            "health": {
                "score": health_score,
                "status": (
                    "healthy"
                    if health_score >= 90
                    else "degraded"
                    if health_score >= 70
                    else "critical"
                ),
            },
            "inventory": source_state,
            "status": {
                "workers": _status_count(workers),
                "pools": _status_count(pools),
                "nodes": _status_count(nodes),
                "miningcore": _status_count(miningcore),
            },
            "alerts": {
                **alert_summary(),
                "active": active_alerts[:25],
            },
            "events": {
                **event_summary(hours=24),
                "recent": events[:25],
            },
            "telemetry": telemetry_summary(),
        }

        home = {
            "generatedAt": started.isoformat(),
            "fleetHealth": health_score,
            "workers": {
                "total": len(workers),
                "status": _status_count(workers),
                "top": workers[:10],
            },
            "pools": {
                "total": len(pools),
                "status": _status_count(pools),
                "items": pools,
            },
            "nodes": {
                "total": len(nodes),
                "status": _status_count(nodes),
                "items": nodes,
            },
            "miningcore": {
                "total": len(miningcore),
                "connected": sum(
                    1
                    for instance in miningcore
                    if instance.get("connected")
                ),
                "items": miningcore,
            },
            "alerts": active_alerts[:10],
            "recentEvents": events[:10],
            "telemetry": telemetry_summary(),
        }

        mining = {
            "generatedAt": started.isoformat(),
            "workers": workers,
            "pools": pools,
            "workloads": workloads,
            "miningcore": miningcore,
            "metricsByEntity": {
                key: value
                for key, value in metric_lookup.items()
                if key.startswith("worker:")
                or key.startswith("pool:")
                or key.startswith("fleet:")
            },
            "activeAlerts": [
                alert
                for alert in active_alerts
                if alert.get("entityType")
                in {
                    "worker",
                    "pool",
                    "miningcore-instance",
                }
            ],
        }

        infrastructure = {
            "generatedAt": started.isoformat(),
            "assets": assets,
            "nodes": nodes,
            "miningcore": miningcore,
            "status": {
                "assets": _status_count(assets),
                "nodes": _status_count(nodes),
                "miningcore": _status_count(miningcore),
            },
            "recentEvents": [
                event
                for event in events
                if event.get("entityType")
                in {
                    "blockchain-node",
                    "miningcore-instance",
                }
            ][:25],
        }

        health = {
            "generatedAt": started.isoformat(),
            "score": health_score,
            "status": overview["health"]["status"],
            "activeAlerts": active_alerts,
            "resourceStatus": overview["status"],
            "telemetry": telemetry_summary(),
        }

        contexts = {
            "overview": overview,
            "home": home,
            "mining": mining,
            "infrastructure": infrastructure,
            "health": health,
        }

        for context_key, payload in contexts.items():
            upsert_context(
                context_key=context_key,
                context_payload=payload,
                source_state=source_state,
            )

        completed = datetime.now(timezone.utc)

        update_builder_state(
            status="ok",
            started_at=started,
            completed_at=completed,
            contexts_written=len(contexts),
        )

        return {
            "status": "ok",
            "source": "nexus-platform-context-builder",
            "contextsWritten": len(contexts),
            "contextKeys": list(contexts),
            "generatedAt": completed.isoformat(),
            "healthScore": health_score,
        }

    except Exception as exc:
        update_builder_state(
            status="error",
            started_at=started,
            completed_at=datetime.now(timezone.utc),
            error=str(exc),
            contexts_written=0,
        )
        raise


def read_context(context_key: str) -> dict[str, Any]:
    record = get_context(context_key)

    if record:
        return {
            "status": "ok",
            "source": "nexus-postgresql-platform-context",
            **record,
        }

    build_contexts()
    record = get_context(context_key)

    return {
        "status": "ok",
        "source": "nexus-postgresql-platform-context",
        **(record or {
            "contextKey": context_key,
            "contextVersion": "v1",
            "generatedAt": None,
            "context": {},
            "sourceState": {},
        }),
    }
