from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from backend.db.connection import get_connection, transaction
from backend.db.repositories.maintenance_repository import (
    active_for_entity,
    cancel_window,
    create_window,
    get_window,
    list_windows,
)


def create(data: dict[str, Any]) -> dict[str, Any]:
    window = create_window(data)
    append_history(
        window["windowId"],
        "scheduled",
        str(data.get("createdBy") or "nexus"),
        "Maintenance window scheduled.",
        {"targets": window.get("targets", [])},
    )
    return window


def append_history(
    window_id: str,
    event_type: str,
    actor: str = "nexus",
    message: str = "",
    details: dict[str, Any] | None = None,
) -> None:
    UUID(str(window_id))
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO nexus.maintenance_history
                   (window_id,event_type,actor,message,details)
                   VALUES(%s,%s,%s,%s,%s)""",
                (window_id, event_type, actor, message, Jsonb(details or {})),
            )


def transition(window_id: str, event_type: str, actor: str = "nexus", message: str = "") -> dict[str, Any]:
    UUID(str(window_id))
    if event_type not in {"started", "completed"}:
        raise ValueError("Unsupported maintenance transition")
    status = "active" if event_type == "started" else "completed"
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE nexus.maintenance_windows
                   SET status=%s, updated_at=NOW(),
                       starts_at=CASE WHEN %s='active' AND starts_at>NOW() THEN NOW() ELSE starts_at END,
                       ends_at=CASE WHEN %s='completed' AND ends_at>NOW() THEN NOW() ELSE ends_at END
                   WHERE window_id=%s AND status <> 'cancelled'
                   RETURNING window_id""",
                (status, status, status, window_id),
            )
            if not cur.fetchone():
                raise KeyError("Maintenance window not found or cancelled")
    append_history(window_id, event_type, actor, message or f"Maintenance {event_type}.")
    return get_window(window_id)


def cancel(window_id: str, actor: str = "nexus", reason: str = "") -> dict[str, Any]:
    window = cancel_window(window_id, actor)
    append_history(window_id, "cancelled", actor, reason or "Maintenance cancelled.")
    return window


def history(window_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    where = "WHERE h.window_id=%s" if window_id else ""
    args: tuple[Any, ...] = (window_id, limit) if window_id else (limit,)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""SELECT h.history_id,h.window_id,h.event_type,h.actor,h.message,
                           h.details,h.occurred_at,w.name AS window_name
                    FROM nexus.maintenance_history h
                    JOIN nexus.maintenance_windows w ON w.window_id=h.window_id
                    {where}
                    ORDER BY h.occurred_at DESC LIMIT %s""",
                args,
            )
            rows = cur.fetchall()
    return [{
        "historyId": row["history_id"],
        "windowId": str(row["window_id"]),
        "windowName": row["window_name"],
        "eventType": row["event_type"],
        "actor": row["actor"],
        "message": row["message"],
        "details": row["details"] or {},
        "occurredAt": row["occurred_at"].isoformat(),
    } for row in rows]


def service_members(service_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT m.asset_id,a.name,a.asset_type,
                          COALESCE(a.operational_state,'unknown') operational_state,
                          m.role,m.required
                   FROM nexus.business_service_members m
                   JOIN nexus.assets a ON a.asset_id=m.asset_id
                   WHERE m.service_id=%s AND COALESCE(m.active,TRUE)=TRUE
                   ORDER BY m.required DESC,a.name""",
                (service_id,),
            )
            return [dict(row) for row in cur.fetchall()]


def active_for_asset(asset_id: str) -> list[dict[str, Any]]:
    direct = active_for_entity("asset", asset_id)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT DISTINCT w.window_id
                   FROM nexus.maintenance_windows w
                   JOIN nexus.maintenance_targets t ON t.window_id=w.window_id
                   JOIN nexus.business_service_members m
                     ON t.target_type='service'
                    AND m.service_id=t.target_value
                    AND COALESCE(m.active,TRUE)=TRUE
                   WHERE m.asset_id=%s
                     AND w.status <> 'cancelled'
                     AND NOW() >= w.starts_at AND NOW() < w.ends_at""",
                (asset_id,),
            )
            ids = [str(row["window_id"]) for row in cur.fetchall()]
    seen = {w["windowId"] for w in direct}
    return direct + [get_window(i) for i in ids if i not in seen]
