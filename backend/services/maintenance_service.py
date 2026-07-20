from __future__ import annotations

from typing import Any

from backend.db.repositories.audit_repository import append_event
from backend.db.repositories.maintenance_repository import (
    active_for_entity,
    cancel_window,
    create_window,
    get_window,
    list_windows,
)


def windows_payload(query: dict[str, list[str]] | None = None) -> dict[str, Any]:
    query = query or {}
    status = (query.get("status") or [None])[0]
    limit = int((query.get("limit") or ["200"])[0])
    windows = list_windows(status=status, limit=limit)
    return {"status": "ok", "source": "nexus-maintenance-windows", "count": len(windows), "windows": windows}


def window_payload(query: dict[str, list[str]]) -> dict[str, Any]:
    window_id = (query.get("windowId") or [""])[0]
    if not window_id:
        raise ValueError("windowId is required")
    return {"status": "ok", "window": get_window(window_id)}


def create_payload(data: dict[str, Any]) -> dict[str, Any]:
    for field in ("startsAt", "endsAt"):
        if not data.get(field):
            raise ValueError(f"{field} is required")
    window = create_window(data)
    append_event({
        "category": "maintenance",
        "action": "maintenance.window.created",
        "source": "maintenance-windows",
        "reason": window["reason"],
        "actor": {"type": "user", "id": window["createdBy"]},
        "metadata": {"windowId": window["windowId"], "targets": window["targets"]},
    })
    return {"status": "ok", "window": window}


def cancel_payload(data: dict[str, Any]) -> dict[str, Any]:
    window_id = str(data.get("windowId") or "")
    if not window_id:
        raise ValueError("windowId is required")
    cancelled_by = str(data.get("cancelledBy") or "nexus")
    window = cancel_window(window_id, cancelled_by)
    append_event({
        "category": "maintenance",
        "action": "maintenance.window.cancelled",
        "source": "maintenance-windows",
        "reason": str(data.get("reason") or ""),
        "actor": {"type": "user", "id": cancelled_by},
        "metadata": {"windowId": window_id},
    })
    return {"status": "ok", "window": window}


def entity_status(entity_type: str, entity_id: str) -> dict[str, Any]:
    windows = active_for_entity(entity_type, entity_id)
    return {
        "inMaintenance": bool(windows),
        "suppressAlerts": any(w["suppressAlerts"] for w in windows),
        "suppressRecommendations": any(w["suppressRecommendations"] for w in windows),
        "windows": windows,
    }


def should_suppress_alert(entity_type: str, entity_id: str) -> bool:
    return entity_status(entity_type, entity_id)["suppressAlerts"]
