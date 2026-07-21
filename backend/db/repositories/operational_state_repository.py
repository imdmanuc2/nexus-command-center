from __future__ import annotations

from typing import Any
from psycopg.types.json import Jsonb

from backend.db.connection import get_connection, transaction

VALID_STATES = {
    "active", "maintenance", "disabled", "provisioning",
    "decommissioning", "retired",
}
SUPPRESSED_STATES = {"maintenance", "disabled", "retired"}


def _normalize_state(value: Any) -> str:
    state = str(value or "").strip().lower()
    if state not in VALID_STATES:
        raise ValueError(f"Unsupported operational state: {state}")
    return state


def _serialize(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "assetId": row["asset_id"],
        "assetType": row["asset_type"],
        "assetName": row["display_name"] or row["name"],
        "lifecycleStatus": row["lifecycle_status"],
        "operationalState": row["operational_state"],
        "operationalStateReason": row["operational_state_reason"],
        "operationalStateChangedAt": row["operational_state_changed_at"].isoformat(),
        "operationalStateChangedBy": row["operational_state_changed_by"],
        "desiredState": row["desired_state"] or {},
        "observedState": row["observed_state"] or {},
        "alertSuppressed": row["operational_state"] in SUPPRESSED_STATES,
    }


def get_asset_state(asset_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT asset_id, asset_type, name, display_name, lifecycle_status,
                       operational_state, operational_state_reason,
                       operational_state_changed_at, operational_state_changed_by,
                       desired_state, observed_state
                FROM nexus.assets WHERE asset_id=%s
            """, (asset_id,))
            row = cur.fetchone()
    if not row:
        raise KeyError("Asset not found")
    return _serialize(row)


def list_asset_states(state: str | None = None, asset_type: str | None = None,
                      limit: int = 500) -> list[dict[str, Any]]:
    clauses, values = [], []
    if state:
        clauses.append("operational_state=%s")
        values.append(_normalize_state(state))
    if asset_type:
        clauses.append("asset_type=%s")
        values.append(asset_type)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    values.append(max(1, min(int(limit), 5000)))
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(f"""
                SELECT asset_id, asset_type, name, display_name, lifecycle_status,
                       operational_state, operational_state_reason,
                       operational_state_changed_at, operational_state_changed_by,
                       desired_state, observed_state
                FROM nexus.assets{where}
                ORDER BY display_name, asset_id LIMIT %s
            """, values)
            rows = cur.fetchall()
    return [_serialize(row) for row in rows]


def set_asset_state(asset_id: str, state: str, *, reason: str = "",
                    changed_by: str = "nexus", source: str = "operational-state",
                    correlation_id: str = "", metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    new_state = _normalize_state(state)
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT operational_state FROM nexus.assets WHERE asset_id=%s FOR UPDATE", (asset_id,))
            current = cur.fetchone()
            if not current:
                raise KeyError("Asset not found")
            previous = current["operational_state"]
            cur.execute("""
                UPDATE nexus.assets
                   SET operational_state=%s,
                       operational_state_reason=%s,
                       operational_state_changed_at=NOW(),
                       operational_state_changed_by=%s,
                       retired_at=CASE WHEN %s='retired' THEN COALESCE(retired_at,NOW()) ELSE NULL END,
                       updated_at=NOW()
                 WHERE asset_id=%s
            """, (new_state, reason, changed_by, new_state, asset_id))
            cur.execute("""
                INSERT INTO nexus.asset_operational_state_history
                  (asset_id,previous_state,new_state,reason,changed_by,source,
                   correlation_id,metadata)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (asset_id, previous, new_state, reason, changed_by, source,
                  correlation_id, Jsonb(metadata or {})))
    return get_asset_state(asset_id)


def bulk_set_asset_state(asset_ids: list[str], state: str, **kwargs: Any) -> list[dict[str, Any]]:
    unique_ids = list(dict.fromkeys(str(v).strip() for v in asset_ids if str(v).strip()))
    if not unique_ids:
        raise ValueError("At least one assetId is required")
    return [set_asset_state(asset_id, state, **kwargs) for asset_id in unique_ids]


def state_history(asset_id: str, limit: int = 100) -> list[dict[str, Any]]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
              SELECT * FROM nexus.asset_operational_state_history
               WHERE asset_id=%s ORDER BY changed_at DESC LIMIT %s
            """, (asset_id, max(1, min(int(limit), 1000))))
            rows = cur.fetchall()
    return [{
        "historyId": row["history_id"], "assetId": row["asset_id"],
        "previousState": row["previous_state"], "newState": row["new_state"],
        "reason": row["reason"], "changedBy": row["changed_by"],
        "source": row["source"], "correlationId": row["correlation_id"],
        "metadata": row["metadata"] or {}, "changedAt": row["changed_at"].isoformat(),
    } for row in rows]


def state_summary() -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT operational_state, COUNT(*) count FROM nexus.assets GROUP BY operational_state")
            counts = {row["operational_state"]: int(row["count"]) for row in cur.fetchall()}
    return {
        "total": sum(counts.values()),
        "byState": {state: counts.get(state, 0) for state in sorted(VALID_STATES)},
        "expectedOfflineStates": sorted(SUPPRESSED_STATES),
    }
