from __future__ import annotations

import hashlib
from typing import Any

from psycopg.types.json import Jsonb

from backend.db.connection import get_connection, transaction


def _session(row):
    return {
        "sessionId": row["session_id"], "runId": row["run_id"],
        "actionId": row["action_id"], "entityType": row["entity_type"],
        "entityId": row["entity_id"], "status": row["status"],
        "currentStage": row["current_stage"],
        "progressPercent": row["progress_percent"],
        "summary": row["summary"], "requestedBy": row["requested_by"],
        "correlationId": row["correlation_id"],
        "startedAt": row["started_at"].isoformat() if row["started_at"] else None,
        "completedAt": row["completed_at"].isoformat() if row["completed_at"] else None,
        "createdAt": row["created_at"].isoformat(),
        "updatedAt": row["updated_at"].isoformat(),
    }


def _event(row):
    return {
        "eventId": row["event_id"], "sessionId": row["session_id"],
        "eventType": row["event_type"], "stage": row["stage"],
        "level": row["level"], "message": row["message"],
        "progressPercent": row["progress_percent"],
        "details": row["details"] or {},
        "occurredAt": row["occurred_at"].isoformat(),
    }


def ensure_session(run: dict[str, Any]):
    run_id = run["runId"]
    session_id = "ops-" + hashlib.sha256(run_id.encode()).hexdigest()[:16]
    correlation_id = str(run.get("inputPayload", {}).get("correlationId") or run_id)
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO nexus.operation_sessions(
                    session_id,run_id,action_id,entity_type,entity_id,status,
                    current_stage,progress_percent,summary,requested_by,correlation_id)
                VALUES(%s,%s,%s,%s,%s,%s,'queued',0,%s,%s,%s)
                ON CONFLICT(run_id) DO UPDATE SET updated_at=NOW()
                RETURNING *
            """, (session_id, run_id, run["actionId"], run["entityType"],
                  run["entityId"], run["status"], "Waiting for execution",
                  run["requestedBy"], correlation_id))
            row = cur.fetchone()
    return _session(row)


def append_event(*, session_id, event_type, stage, message,
                 progress_percent=None, level="info", details=None,
                 session_status=None, summary=None):
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO nexus.operation_session_events(
                    session_id,event_type,stage,level,message,progress_percent,details)
                VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING *
            """, (session_id, event_type, stage, level, message,
                  progress_percent, Jsonb(details or {})))
            event = cur.fetchone()
            sets = ["current_stage=%s", "updated_at=NOW()"]
            values = [stage]
            if progress_percent is not None:
                sets.append("progress_percent=%s"); values.append(progress_percent)
            if session_status is not None:
                sets.append("status=%s"); values.append(session_status)
                if session_status == "running": sets.append("started_at=COALESCE(started_at,NOW())")
                if session_status in {"completed","failed","cancelled","rejected"}: sets.append("completed_at=NOW()")
            if summary is not None:
                sets.append("summary=%s"); values.append(summary)
            values.append(session_id)
            cur.execute(f"UPDATE nexus.operation_sessions SET {', '.join(sets)} WHERE session_id=%s", tuple(values))
    return _event(event)


def get_session_by_run(run_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM nexus.operation_sessions WHERE run_id=%s", (run_id,))
            row = cur.fetchone()
    return _session(row) if row else None


def get_session(session_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM nexus.operation_sessions WHERE session_id=%s", (session_id,))
            row = cur.fetchone()
    return _session(row) if row else None


def list_events(session_id, after_event_id=0, limit=500):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM nexus.operation_session_events
                WHERE session_id=%s AND event_id>%s
                ORDER BY event_id ASC LIMIT %s
            """, (session_id, max(0, int(after_event_id)), max(1, min(int(limit), 1000))))
            rows = cur.fetchall()
    return [_event(row) for row in rows]


def list_sessions(limit=100):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM nexus.operation_sessions ORDER BY updated_at DESC LIMIT %s", (max(1,min(int(limit),500)),))
            rows = cur.fetchall()
    return [_session(row) for row in rows]
