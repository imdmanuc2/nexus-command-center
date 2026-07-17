
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.db.repositories.alert_repository import (
    alert_summary,
    list_alerts,
)
from backend.db.repositories.automation_repository import (
    automation_summary,
    list_runs,
)
from backend.db.repositories.operations_center_repository import (
    latest_operations_snapshot,
    save_operations_snapshot,
)
from backend.db.repositories.recommendation_repository import (
    list_recommendations,
    recommendation_summary,
)
from backend.db.repositories.timeline_repository import (
    list_entries,
    summary as timeline_summary,
)
from backend.services.fleet_service import fleet
from backend.services.topology_service import topology


def _status_from_score(score: float) -> str:
    if score >= 90:
        return "healthy"
    if score >= 70:
        return "degraded"
    if score >= 40:
        return "warning"
    return "critical"


def _queue_breakdown(runs: list[dict[str, Any]]) -> dict[str, Any]:
    buckets = {
        "pendingApproval": [],
        "queued": [],
        "running": [],
        "completed": [],
        "failed": [],
        "rejected": [],
        "cancelled": [],
    }

    mapping = {
        "pending-approval": "pendingApproval",
        "queued": "queued",
        "running": "running",
        "completed": "completed",
        "failed": "failed",
        "rejected": "rejected",
        "cancelled": "cancelled",
    }

    for run in runs:
        key = mapping.get(run.get("status"))
        if key:
            buckets[key].append(run)

    return {
        **{
            f"{key}Count": len(value)
            for key, value in buckets.items()
        },
        **buckets,
    }


def build_operations_center(
    *,
    persist: bool = True,
) -> dict[str, Any]:
    fleet_state = fleet()
    topology_state = topology()
    alerts = list_alerts(limit=250)
    recommendations = list_recommendations(limit=250)
    runs = list_runs(limit=250)
    timeline = list_entries(limit=50)

    active_alerts = [
        alert
        for alert in alerts
        if alert.get("status") in {
            "open",
            "acknowledged",
        }
    ]

    critical_alerts = [
        alert
        for alert in active_alerts
        if alert.get("severity") == "critical"
    ]

    warning_alerts = [
        alert
        for alert in active_alerts
        if alert.get("severity") == "warning"
    ]

    high_priority_recommendations = [
        item
        for item in recommendations
        if item.get("status") in {
            "open",
            "accepted",
        }
        and item.get("priority") in {
            "critical",
            "high",
        }
    ]

    queue = _queue_breakdown(runs)

    fleet_health = float(
        fleet_state.get("fleetHealth")
        or 100
    )

    deductions = (
        len(critical_alerts) * 20
        + len(warning_alerts) * 5
        + queue["failedCount"] * 10
        + queue["runningCount"] * 1
        + queue["pendingApprovalCount"] * 1
    )

    health_score = max(
        0.0,
        min(100.0, round(fleet_health - deductions, 2)),
    )

    overall_status = _status_from_score(
        health_score
    )

    worker_count = int(
        (fleet_state.get("workers") or {}).get(
            "active",
            0,
        )
    )

    topology_counts = (
        topology_state.get("counts")
        or {}
    )

    payload = {
        "status": "ok",
        "source": "nexus-operations-center-platform",
        "generatedAt": datetime.now(
            timezone.utc
        ).isoformat(),
        "overall": {
            "status": overall_status,
            "healthScore": health_score,
            "fleetHealth": fleet_health,
            "activeAlerts": len(active_alerts),
            "criticalAlerts": len(critical_alerts),
            "highPriorityRecommendations":
                len(high_priority_recommendations),
            "pendingApprovals":
                queue["pendingApprovalCount"],
            "runningOperations":
                queue["runningCount"],
            "failedOperations":
                queue["failedCount"],
        },
        "infrastructure": {
            "assets": (
                fleet_state.get("assets")
                or {}
            ),
            "workers": (
                fleet_state.get("workers")
                or {}
            ),
            "pools": (
                fleet_state.get("pools")
                or {}
            ),
            "workloads": (
                fleet_state.get("workloads")
                or {}
            ),
            "topology": topology_counts,
            "workerCountMatchesTopology": (
                worker_count
                == int(
                    topology_counts.get(
                        "workers",
                        0,
                    )
                )
            ),
        },
        "mining": {
            "fleetHashrate":
                fleet_state.get("fleetHashrate", 0),
            "hashrateUnit":
                fleet_state.get("hashrateUnit", "H/s"),
            "compute":
                fleet_state.get("compute") or {},
        },
        "alerts": {
            "summary": alert_summary(),
            "active": active_alerts[:25],
        },
        "recommendations": {
            "summary": recommendation_summary(),
            "highPriority":
                high_priority_recommendations[:25],
        },
        "operations": {
            "summary": automation_summary(),
            "queue": queue,
            "recentRuns": runs[:25],
        },
        "timeline": {
            "summary": timeline_summary(24),
            "latest": timeline,
        },
        "quickActions": [
            {
                "actionId": "refresh-platform-sync",
                "label": "Refresh Platform State",
                "description": "Run the full PostgreSQL Platform synchronization pipeline now.",
                "entityType": "platform",
                "entityId": "primary",
                "riskLevel": "low",
                "supportsDryRun": True,
                "requiresApproval": False,
            },
            {
                "actionId": "refresh-resource-sync",
                "label": "Refresh Resource Persistence",
                "description": "Refresh blockchain node and MiningCore resource persistence.",
                "entityType": "platform",
                "entityId": "primary",
                "riskLevel": "low",
                "supportsDryRun": True,
                "requiresApproval": False,
            },
            {
                "actionId": "test-blockchain-rpc",
                "label": "Test Blockchain RPC",
                "description": "Create an audited, non-destructive RPC test request.",
                "entityType": "blockchain-node",
                "entityId": "primary",
                "riskLevel": "low",
                "supportsDryRun": True,
                "requiresApproval": False,
            },
        ],
    }

    if persist:
        save_operations_snapshot(
            snapshot_key="primary",
            health_score=health_score,
            overall_status=overall_status,
            payload=payload,
        )

    return payload


def operations_status() -> dict[str, Any]:
    state = build_operations_center(
        persist=False,
    )

    return {
        "status": state["status"],
        "source": state["source"],
        "generatedAt": state["generatedAt"],
        "overall": state["overall"],
        "infrastructure": state["infrastructure"],
        "mining": state["mining"],
    }


def operations_queue() -> dict[str, Any]:
    runs = list_runs(limit=250)
    queue = _queue_breakdown(runs)

    return {
        "status": "ok",
        "source":
            "nexus-operations-center-platform",
        "count": len(runs),
        "queue": queue,
    }


def latest_snapshot() -> dict[str, Any]:
    snapshot = latest_operations_snapshot(
        "primary"
    )

    return {
        "status": "ok",
        "source":
            "nexus-postgresql-operations-center",
        "snapshot": snapshot,
    }
