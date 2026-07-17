"""PostgreSQL repository for immutable Nexus audit events."""
from __future__ import annotations
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
from psycopg.types.json import Jsonb
from backend.db.connection import get_connection

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def append_event(event: dict[str, Any]) -> dict[str, Any]:
    actor = event.get("actor") or {}
    rec = {
        "event_id": event.get("eventId") or f"audit-{uuid4().hex}",
        "occurred_at": event.get("timestamp") or now_iso(),
        "category": event.get("category") or "cmdb",
        "action": event.get("action") or "unknown",
        "asset_id": event.get("assetId") or None,
        "asset_type": event.get("assetType") or "",
        "asset_name": event.get("assetName") or "",
        "actor_type": actor.get("type") or "system",
        "actor_id": actor.get("id") or "nexus",
        "source": event.get("source") or "cmdb",
        "reason": event.get("reason") or "",
        "correlation_id": event.get("correlationId") or f"corr-{uuid4().hex}",
        "confidence": event.get("confidence"),
        "changes": Jsonb(event.get("changes") or []),
        "metadata": Jsonb(event.get("metadata") or {}),
    }
    with get_connection() as c:
        with c.cursor() as cur:
            cur.execute("""
                INSERT INTO nexus.audit_events (
                  event_id, occurred_at, category, action, asset_id, asset_type,
                  asset_name, actor_type, actor_id, source, reason, correlation_id,
                  confidence, changes, metadata
                ) VALUES (
                  %(event_id)s, %(occurred_at)s::timestamptz, %(category)s,
                  %(action)s, %(asset_id)s, %(asset_type)s, %(asset_name)s,
                  %(actor_type)s, %(actor_id)s, %(source)s, %(reason)s,
                  %(correlation_id)s, %(confidence)s, %(changes)s, %(metadata)s
                )
                ON CONFLICT (event_id) DO NOTHING
            """, rec)
        c.commit()
    return event | {"eventId": rec["event_id"], "timestamp": rec["occurred_at"],
                    "correlationId": rec["correlation_id"]}

def read_events(asset_id=None, action=None, source=None, correlation_id=None, limit=200):
    clauses, vals = [], []
    for col, val in [("asset_id", asset_id), ("action", action),
                     ("source", source), ("correlation_id", correlation_id)]:
        if val:
            clauses.append(f"{col}=%s"); vals.append(val)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    vals.append(max(1, min(int(limit), 5000)))
    with get_connection() as c:
        with c.cursor() as cur:
            cur.execute(f"SELECT * FROM nexus.audit_events{where} ORDER BY occurred_at DESC LIMIT %s", vals)
            rows = cur.fetchall()
    return [{
      "eventId": r["event_id"], "timestamp": r["occurred_at"].isoformat(),
      "category": r["category"], "action": r["action"],
      "assetId": r["asset_id"] or "", "assetType": r["asset_type"],
      "assetName": r["asset_name"], "actor": {"type": r["actor_type"], "id": r["actor_id"]},
      "source": r["source"], "reason": r["reason"], "correlationId": r["correlation_id"],
      "confidence": float(r["confidence"]) if r["confidence"] is not None else None,
      "changes": r["changes"] or [], "metadata": r["metadata"] or {}
    } for r in rows]

def summary():
    with get_connection() as c:
        with c.cursor() as cur:
            cur.execute("""SELECT COUNT(*) event_count,
                COUNT(DISTINCT asset_id) FILTER (WHERE asset_id IS NOT NULL) changed_asset_count,
                MAX(occurred_at) latest_event_at FROM nexus.audit_events""")
            t = cur.fetchone()
            cur.execute("SELECT action, COUNT(*) count FROM nexus.audit_events GROUP BY action")
            by_action = {r["action"]: int(r["count"]) for r in cur.fetchall()}
            cur.execute("SELECT source, COUNT(*) count FROM nexus.audit_events GROUP BY source")
            by_source = {r["source"]: int(r["count"]) for r in cur.fetchall()}
    return {"eventCount": int(t["event_count"]), "changedAssetCount": int(t["changed_asset_count"]),
            "byAction": by_action, "bySource": by_source,
            "latestEventAt": t["latest_event_at"].isoformat() if t["latest_event_at"] else None}
