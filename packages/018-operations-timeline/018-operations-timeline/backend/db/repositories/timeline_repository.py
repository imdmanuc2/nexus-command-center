from __future__ import annotations
from datetime import datetime
from typing import Any
from psycopg.types.json import Jsonb
from backend.db.connection import get_connection, transaction

def state():
    with get_connection() as c:
        with c.cursor() as cur:
            cur.execute("SELECT * FROM nexus.timeline_engine_state WHERE engine_name='operations-timeline'")
            row = cur.fetchone()
    return row or {
        "last_platform_event_id": 0,
        "last_alert_seen_at": None,
        "last_recommendation_seen_at": None,
        "last_automation_seen_at": None,
    }

def append(*, source_type, source_id, event_type, severity,
           entity_type, entity_id, title, message, data, occurred_at):
    with transaction() as c:
        with c.cursor() as cur:
            cur.execute("""
                INSERT INTO nexus.operations_timeline(
                    source_type,source_id,event_type,severity,
                    entity_type,entity_id,title,message,data,occurred_at)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(source_type,source_id) DO NOTHING
            """, (
                source_type, source_id, event_type, severity,
                entity_type, entity_id, title, message,
                Jsonb(data), occurred_at
            ))
            return cur.rowcount == 1

def remember(*, entity_type, entity_id, payload, state_hash, observed_at):
    with transaction() as c:
        with c.cursor() as cur:
            cur.execute("""
                INSERT INTO nexus.asset_state_history(
                    entity_type,entity_id,state_payload,state_hash,observed_at)
                VALUES(%s,%s,%s,%s,%s)
                ON CONFLICT(entity_type,entity_id,state_hash) DO NOTHING
            """, (entity_type, entity_id, Jsonb(payload), state_hash, observed_at))

def save_state(*, event_id, alert_at, rec_at, automation_at,
               status, error, written):
    with transaction() as c:
        with c.cursor() as cur:
            cur.execute("""
                INSERT INTO nexus.timeline_engine_state(
                    engine_name,last_platform_event_id,last_alert_seen_at,
                    last_recommendation_seen_at,last_automation_seen_at,
                    last_status,last_error,entries_written,updated_at)
                VALUES('operations-timeline',%s,%s,%s,%s,%s,%s,%s,NOW())
                ON CONFLICT(engine_name) DO UPDATE SET
                    last_platform_event_id=EXCLUDED.last_platform_event_id,
                    last_alert_seen_at=EXCLUDED.last_alert_seen_at,
                    last_recommendation_seen_at=EXCLUDED.last_recommendation_seen_at,
                    last_automation_seen_at=EXCLUDED.last_automation_seen_at,
                    last_status=EXCLUDED.last_status,
                    last_error=EXCLUDED.last_error,
                    entries_written=EXCLUDED.entries_written,
                    updated_at=NOW()
            """, (event_id, alert_at, rec_at, automation_at,
                  status, error, written))

def list_entries(limit=100):
    with get_connection() as c:
        with c.cursor() as cur:
            cur.execute("""
                SELECT * FROM nexus.operations_timeline
                ORDER BY occurred_at DESC,timeline_id DESC LIMIT %s
            """, (max(1, min(limit, 1000)),))
            rows = cur.fetchall()
    return [{
        "timelineId": r["timeline_id"], "sourceType": r["source_type"],
        "sourceId": r["source_id"], "eventType": r["event_type"],
        "severity": r["severity"], "entityType": r["entity_type"],
        "entityId": r["entity_id"], "title": r["title"],
        "message": r["message"], "data": r["data"] or {},
        "occurredAt": r["occurred_at"].isoformat()
    } for r in rows]

def summary(hours=24):
    with get_connection() as c:
        with c.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) entry_count,
                       COUNT(DISTINCT entity_type||':'||entity_id) entity_count,
                       MAX(occurred_at) latest_at
                FROM nexus.operations_timeline
                WHERE occurred_at >= NOW()-(%s*INTERVAL '1 hour')
            """, (hours,))
            r = cur.fetchone()
    return {
        "hours": hours, "entryCount": r["entry_count"],
        "entityCount": r["entity_count"],
        "latestAt": r["latest_at"].isoformat() if r["latest_at"] else None
    }
