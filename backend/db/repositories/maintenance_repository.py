from __future__ import annotations

from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from backend.db.connection import get_connection, transaction

VALID_TARGET_TYPES = {"asset", "asset_type", "site", "rack", "pool", "cluster", "tag", "service"}


def _serialize(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "windowId": str(row["window_id"]),
        "name": row["name"],
        "description": row["description"],
        "status": row["effective_status"],
        "storedStatus": row["status"],
        "startsAt": row["starts_at"].isoformat(),
        "endsAt": row["ends_at"].isoformat(),
        "createdBy": row["created_by"],
        "reason": row["reason"],
        "suppressAlerts": row["suppress_alerts"],
        "suppressRecommendations": row["suppress_recommendations"],
        "metadata": row["metadata"] or {},
        "targets": row.get("targets") or [],
        "createdAt": row["created_at"].isoformat(),
        "updatedAt": row["updated_at"].isoformat(),
    }


def create_window(data: dict[str, Any]) -> dict[str, Any]:
    targets = data.get("targets") or []
    if not targets:
        raise ValueError("At least one maintenance target is required")
    for target in targets:
        if target.get("type") not in VALID_TARGET_TYPES:
            raise ValueError(f"Unsupported target type: {target.get('type')}")
        if not str(target.get("value") or "").strip():
            raise ValueError("Every maintenance target requires a value")

    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO nexus.maintenance_windows
                  (name, description, starts_at, ends_at, created_by, reason,
                   suppress_alerts, suppress_recommendations, metadata)
                VALUES (%s,%s,%s::timestamptz,%s::timestamptz,%s,%s,%s,%s,%s)
                RETURNING window_id
                """,
                (
                    str(data.get("name") or "Maintenance Window").strip(),
                    str(data.get("description") or ""),
                    data["startsAt"], data["endsAt"],
                    str(data.get("createdBy") or "nexus"),
                    str(data.get("reason") or ""),
                    bool(data.get("suppressAlerts", True)),
                    bool(data.get("suppressRecommendations", True)),
                    Jsonb(data.get("metadata") or {}),
                ),
            )
            window_id = cur.fetchone()["window_id"]
            for target in targets:
                cur.execute(
                    """INSERT INTO nexus.maintenance_targets
                       (window_id,target_type,target_value,metadata)
                       VALUES(%s,%s,%s,%s)""",
                    (window_id, target["type"], str(target["value"]), Jsonb(target.get("metadata") or {})),
                )
    return get_window(str(window_id))


def _base_query() -> str:
    return """
      SELECT w.*,
        CASE
          WHEN w.status='cancelled' THEN 'cancelled'
          WHEN NOW() < w.starts_at THEN 'scheduled'
          WHEN NOW() >= w.ends_at THEN 'completed'
          ELSE 'active'
        END AS effective_status,
        COALESCE((SELECT jsonb_agg(jsonb_build_object(
          'targetId',t.target_id,'type',t.target_type,'value',t.target_value,'metadata',t.metadata)
          ORDER BY t.target_id) FROM nexus.maintenance_targets t WHERE t.window_id=w.window_id),'[]'::jsonb) AS targets
      FROM nexus.maintenance_windows w
    """


def get_window(window_id: str) -> dict[str, Any]:
    UUID(window_id)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(_base_query() + " WHERE w.window_id=%s", (window_id,))
            row = cur.fetchone()
    if not row:
        raise KeyError("Maintenance window not found")
    return _serialize(row)


def list_windows(status: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    sql = _base_query()
    values: list[Any] = []
    if status:
        sql = f"SELECT * FROM ({sql}) q WHERE q.effective_status=%s"
        values.append(status)
    sql += " ORDER BY starts_at DESC LIMIT %s"
    values.append(max(1, min(int(limit), 1000)))
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, values)
            rows = cur.fetchall()
    return [_serialize(row) for row in rows]


def cancel_window(window_id: str, cancelled_by: str = "nexus") -> dict[str, Any]:
    UUID(window_id)
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE nexus.maintenance_windows
                   SET status='cancelled', cancelled_at=NOW(), updated_at=NOW(),
                       metadata=metadata || %s
                   WHERE window_id=%s AND status <> 'cancelled'
                   RETURNING window_id""",
                (Jsonb({"cancelledBy": cancelled_by}), window_id),
            )
            if not cur.fetchone():
                raise KeyError("Maintenance window not found or already cancelled")
    return get_window(window_id)


def active_for_entity(entity_type: str, entity_id: str) -> list[dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT w.*,
                  'active' AS effective_status,
                  COALESCE((SELECT jsonb_agg(jsonb_build_object(
                    'targetId',mt.target_id,'type',mt.target_type,'value',mt.target_value,'metadata',mt.metadata)
                    ORDER BY mt.target_id) FROM nexus.maintenance_targets mt WHERE mt.window_id=w.window_id),'[]'::jsonb) targets
                FROM nexus.maintenance_windows w
                JOIN nexus.maintenance_targets t ON t.window_id=w.window_id
                LEFT JOIN nexus.assets a ON a.asset_id=%s
                WHERE w.status <> 'cancelled'
                  AND NOW() >= w.starts_at AND NOW() < w.ends_at
                  AND (
                    (t.target_type='asset' AND t.target_value=%s)
                    OR (t.target_type='asset_type' AND (t.target_value=%s OR t.target_value=COALESCE(a.asset_type,'')))
                    OR (t.target_type='site' AND t.target_value=COALESCE(a.location,''))
                    OR (t.target_type='rack' AND t.target_value=COALESCE(a.rack,''))
                    OR (t.target_type='pool' AND (t.target_value=%s OR t.target_value=COALESCE(a.metadata->>'poolId','')))
                    OR (t.target_type='cluster' AND t.target_value=COALESCE(a.metadata->>'cluster',''))
                    OR (t.target_type='tag' AND COALESCE(a.metadata->'tags','[]'::jsonb) ? t.target_value)
                  )
                ORDER BY w.starts_at
                """,
                (entity_id, entity_id, entity_type, entity_id),
            )
            rows = cur.fetchall()
    return [_serialize(row) for row in rows]
