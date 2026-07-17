from __future__ import annotations

import hashlib
import json
from typing import Any

from psycopg.types.json import Jsonb

from backend.db.connection import get_connection, transaction


def _action(row):
    return {
        "actionId": row["action_id"], "name": row["name"],
        "description": row["description"], "actionType": row["action_type"],
        "entityType": row["entity_type"], "riskLevel": row["risk_level"],
        "requiresApproval": row["requires_approval"],
        "supportsDryRun": row["supports_dry_run"],
        "timeoutSeconds": row["timeout_seconds"], "retryLimit": row["retry_limit"],
        "commandTemplate": row["command_template"] or {},
        "metadata": row["metadata"] or {},
    }


def _run(row):
    return {
        "runId": row["run_id"], "actionId": row["action_id"],
        "recommendationId": row["recommendation_id"],
        "entityType": row["entity_type"], "entityId": row["entity_id"],
        "status": row["status"], "requestedBy": row["requested_by"],
        "approvedBy": row["approved_by"], "dryRun": row["dry_run"],
        "attemptCount": row["attempt_count"],
        "inputPayload": row["input_payload"] or {},
        "executionPlan": row["execution_plan"] or {},
        "resultPayload": row["result_payload"] or {},
        "errorMessage": row["error_message"],
        "requestedAt": row["requested_at"].isoformat(),
        "approvedAt": row["approved_at"].isoformat() if row["approved_at"] else None,
        "startedAt": row["started_at"].isoformat() if row["started_at"] else None,
        "completedAt": row["completed_at"].isoformat() if row["completed_at"] else None,
    }


def list_actions():
    with get_connection() as c:
        with c.cursor() as cur:
            cur.execute("SELECT * FROM nexus.automation_actions WHERE enabled=TRUE ORDER BY risk_level,name")
            rows = cur.fetchall()
    return [_action(r) for r in rows]


def get_action(action_id):
    with get_connection() as c:
        with c.cursor() as cur:
            cur.execute("SELECT * FROM nexus.automation_actions WHERE action_id=%s AND enabled=TRUE", (action_id,))
            row = cur.fetchone()
    return _action(row) if row else None


def get_run(run_id):
    with get_connection() as c:
        with c.cursor() as cur:
            cur.execute("SELECT * FROM nexus.automation_runs WHERE run_id=%s", (run_id,))
            row = cur.fetchone()
    return _run(row) if row else None


def record_control_event(*, run_id, action_id, control_action, actor,
                         previous_status, new_status, message='', details=None):
    with transaction() as c:
        with c.cursor() as cur:
            cur.execute("""
                INSERT INTO nexus.automation_control_audit(
                    run_id,action_id,control_action,actor,previous_status,
                    new_status,message,details)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
            """, (run_id, action_id, control_action, actor, previous_status,
                  new_status, message, Jsonb(details or {})))


def create_run(*, action_id, recommendation_id, entity_type, entity_id,
               requested_by, dry_run, input_payload, execution_plan,
               requires_approval):
    raw = json.dumps({"a": action_id, "r": recommendation_id, "t": entity_type,
                      "e": entity_id, "u": requested_by, "d": dry_run,
                      "i": input_payload}, sort_keys=True, default=str)
    run_id = "run-" + hashlib.sha256(raw.encode()).hexdigest()[:16]
    status = "pending-approval" if requires_approval and not dry_run else "queued"
    with transaction() as c:
        with c.cursor() as cur:
            cur.execute("""
                INSERT INTO nexus.automation_runs(
                    run_id,action_id,recommendation_id,entity_type,entity_id,
                    status,requested_by,dry_run,input_payload,execution_plan)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT(run_id) DO UPDATE SET updated_at=NOW()
                RETURNING *
            """, (run_id, action_id, recommendation_id, entity_type, entity_id,
                  status, requested_by, dry_run, Jsonb(input_payload),
                  Jsonb(execution_plan)))
            row = cur.fetchone()
    record_control_event(run_id=run_id, action_id=action_id,
                         control_action="requested", actor=requested_by,
                         previous_status="", new_status=status,
                         message="Automation run requested.",
                         details={"dryRun": dry_run, "entityType": entity_type,
                                  "entityId": entity_id})
    return _run(row)


def list_runs(limit=100):
    with get_connection() as c:
        with c.cursor() as cur:
            cur.execute("SELECT * FROM nexus.automation_runs ORDER BY requested_at DESC LIMIT %s", (max(1, min(limit, 1000)),))
            rows = cur.fetchall()
    return [_run(r) for r in rows]


def list_queued_runs(limit=25):
    with get_connection() as c:
        with c.cursor() as cur:
            cur.execute("SELECT * FROM nexus.automation_runs WHERE status='queued' ORDER BY requested_at LIMIT %s", (max(1, min(limit, 250)),))
            rows = cur.fetchall()
    return [_run(r) for r in rows]


def approve_run(*, run_id, approved_by, message=''):
    with transaction() as c:
        with c.cursor() as cur:
            cur.execute("""
                UPDATE nexus.automation_runs SET status='queued',approved_by=%s,
                    approved_at=NOW(),updated_at=NOW()
                WHERE run_id=%s AND status='pending-approval' RETURNING *
            """, (approved_by, run_id))
            row = cur.fetchone()
    if not row:
        return None
    result = _run(row)
    record_control_event(run_id=run_id, action_id=result["actionId"],
                         control_action="approved", actor=approved_by,
                         previous_status="pending-approval", new_status="queued",
                         message=message or "Automation run approved.")
    return result


def reject_run(*, run_id, rejected_by, message=''):
    with transaction() as c:
        with c.cursor() as cur:
            cur.execute("""
                UPDATE nexus.automation_runs SET status='rejected',approved_by=%s,
                    result_payload=%s,completed_at=NOW(),updated_at=NOW()
                WHERE run_id=%s AND status='pending-approval' RETURNING *
            """, (rejected_by, Jsonb({"rejected": True, "reason": message}), run_id))
            row = cur.fetchone()
    if not row:
        return None
    result = _run(row)
    record_control_event(run_id=run_id, action_id=result["actionId"],
                         control_action="rejected", actor=rejected_by,
                         previous_status="pending-approval", new_status="rejected",
                         message=message or "Automation run rejected.")
    return result


def cancel_run(*, run_id, cancelled_by, message=''):
    with transaction() as c:
        with c.cursor() as cur:
            cur.execute("""
                UPDATE nexus.automation_runs SET status='cancelled',
                    result_payload=%s,completed_at=NOW(),updated_at=NOW()
                WHERE run_id=%s AND status IN ('pending-approval','queued') RETURNING *
            """, (Jsonb({"cancelled": True, "cancelledBy": cancelled_by,
                          "reason": message}), run_id))
            row = cur.fetchone()
    if not row:
        return None
    result = _run(row)
    record_control_event(run_id=run_id, action_id=result["actionId"],
                         control_action="cancelled", actor=cancelled_by,
                         previous_status="pending-approval-or-queued",
                         new_status="cancelled",
                         message=message or "Automation run cancelled.")
    return result


def mark_run_running(run_id):
    with transaction() as c:
        with c.cursor() as cur:
            cur.execute("""
                UPDATE nexus.automation_runs SET status='running',
                    attempt_count=attempt_count+1,started_at=NOW(),updated_at=NOW()
                WHERE run_id=%s AND status='queued' RETURNING action_id
            """, (run_id,))
            row = cur.fetchone()
    if not row:
        return False
    record_control_event(run_id=run_id, action_id=row["action_id"],
                         control_action="started", actor="automation-engine",
                         previous_status="queued", new_status="running",
                         message="Automation execution started.")
    return True


def complete_run(*, run_id, status, result_payload, error_message=''):
    with transaction() as c:
        with c.cursor() as cur:
            cur.execute("""
                UPDATE nexus.automation_runs SET status=%s,result_payload=%s,
                    error_message=%s,completed_at=NOW(),updated_at=NOW()
                WHERE run_id=%s RETURNING action_id
            """, (status, Jsonb(result_payload), error_message, run_id))
            row = cur.fetchone()
    if row:
        record_control_event(run_id=run_id, action_id=row["action_id"],
                             control_action="completed" if status == "completed" else "failed",
                             actor="automation-engine", previous_status="running",
                             new_status=status,
                             message="Automation execution completed." if status == "completed" else (error_message or "Automation execution failed."),
                             details=result_payload)


def list_control_audit(run_id=None, limit=100):
    query = "SELECT * FROM nexus.automation_control_audit"
    params = []
    if run_id:
        query += " WHERE run_id=%s"
        params.append(run_id)
    query += " ORDER BY occurred_at DESC,audit_id DESC LIMIT %s"
    params.append(max(1, min(limit, 1000)))
    with get_connection() as c:
        with c.cursor() as cur:
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
    return [{"auditId": r["audit_id"], "runId": r["run_id"],
             "actionId": r["action_id"], "controlAction": r["control_action"],
             "actor": r["actor"], "previousStatus": r["previous_status"],
             "newStatus": r["new_status"], "message": r["message"],
             "details": r["details"] or {}, "occurredAt": r["occurred_at"].isoformat()}
            for r in rows]


def automation_summary():
    with get_connection() as c:
        with c.cursor() as cur:
            cur.execute("""
                SELECT COUNT(*) FILTER(WHERE status='pending-approval') pending_approval,
                       COUNT(*) FILTER(WHERE status='queued') queued,
                       COUNT(*) FILTER(WHERE status='running') running,
                       COUNT(*) FILTER(WHERE status='completed') completed,
                       COUNT(*) FILTER(WHERE status='failed') failed,
                       COUNT(*) FILTER(WHERE status='rejected') rejected,
                       COUNT(*) FILTER(WHERE status='cancelled') cancelled
                FROM nexus.automation_runs
            """)
            r = cur.fetchone()
    return {"pendingApproval": r["pending_approval"], "queued": r["queued"],
            "running": r["running"], "completed": r["completed"],
            "failed": r["failed"], "rejected": r["rejected"],
            "cancelled": r["cancelled"]}
