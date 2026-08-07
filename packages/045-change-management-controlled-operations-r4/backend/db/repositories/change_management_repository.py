from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from backend.db.connection import get_connection, transaction

def operation_queue_available(conn=None) -> bool:
    own = conn is None
    connection = conn or get_connection()
    try:
        with connection.cursor() as cur:
            cur.execute("SELECT to_regclass('nexus.operation_queue') IS NOT NULL AS available")
            return bool(cur.fetchone()["available"])
    finally:
        if own:
            connection.close()



def _change_number(cur) -> str:
    cur.execute("SELECT nextval('nexus.change_number_seq') AS n")
    return f"CHG-{int(cur.fetchone()['n']):06d}"


def append_log(change_id: str, event_type: str, actor: str, message: str, details=None, conn=None):
    UUID(str(change_id))
    own = conn is None
    connection = conn or get_connection()
    try:
        with connection.cursor() as cur:
            cur.execute(
                """INSERT INTO nexus.change_execution_log
                   (change_id,event_type,actor,message,details)
                   VALUES(%s,%s,%s,%s,%s)""",
                (change_id,event_type,actor,message,Jsonb(details or {})),
            )
        if own:
            connection.commit()
    finally:
        if own:
            connection.close()


def list_templates(active_only=True):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT * FROM nexus.change_templates
                   WHERE (%s=FALSE OR active=TRUE)
                   ORDER BY risk_level,name""",
                (active_only,),
            )
            return [dict(r) for r in cur.fetchall()]


def get_template(template_id: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM nexus.change_templates WHERE template_id=%s", (template_id,))
            row = cur.fetchone()
    if not row:
        raise KeyError("Change template not found")
    return dict(row)


def create_change(data: dict[str, Any], impact: dict[str, Any], maintenance: dict[str, Any]):
    template_id = str(data.get("templateId") or "")
    template = get_template(template_id) if template_id else {}
    title = str(data.get("title") or template.get("name") or "Controlled operation").strip()
    capability = str(data.get("capability") or template.get("capability") or "").strip()
    target_id = str(data.get("targetId") or "").strip()
    target_type = str(data.get("targetType") or template.get("target_type") or "asset").strip()
    if not title or not capability or not target_id:
        raise ValueError("title, capability, and targetId are required")

    risk = str(data.get("riskLevel") or template.get("risk_level") or "medium")
    approval_required = bool(data.get("approvalRequired", template.get("approval_required", True)))
    maintenance_required = bool(data.get("maintenanceRequired", template.get("maintenance_required", False)))
    status = "pending-approval" if approval_required else "approved"
    params = {**(template.get("default_parameters") or {}), **(data.get("parameters") or {})}
    actor = str(data.get("requestedBy") or "operator")
    correlation_id = str(data.get("correlationId") or uuid4())

    with transaction() as conn:
        with conn.cursor() as cur:
            number = _change_number(cur)
            cur.execute(
                """INSERT INTO nexus.change_requests
                   (change_number,title,description,template_id,capability,rollback_capability,
                    target_type,target_id,asset_id,service_id,maintenance_window_id,status,
                    risk_level,approval_required,maintenance_required,requested_by,parameters,
                    impact_snapshot,maintenance_snapshot,correlation_id,scheduled_for)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   RETURNING change_id""",
                (
                    number,title,str(data.get("description") or ""),template_id or None,capability,
                    str(data.get("rollbackCapability") or template.get("rollback_capability") or ""),
                    target_type,target_id,data.get("assetId") or (target_id if target_type=="asset" else None),
                    data.get("serviceId") or None,data.get("maintenanceWindowId") or None,status,
                    risk,approval_required,maintenance_required,actor,Jsonb(params),
                    Jsonb(impact),Jsonb(maintenance),correlation_id,data.get("scheduledFor") or None,
                ),
            )
            change_id = str(cur.fetchone()["change_id"])
            steps = [
                ("Validate target and capability","validation"),
                ("Validate maintenance and approval","control-gate"),
                ("Queue controlled operation",capability),
                ("Post-action health verification","health-check"),
            ]
            for pos,(name,cap) in enumerate(steps,1):
                cur.execute(
                    """INSERT INTO nexus.change_steps(change_id,position,name,capability)
                       VALUES(%s,%s,%s,%s)""",
                    (change_id,pos,name,cap),
                )
            append_log(change_id,"created",actor,"Change request created.",
                       {"status":status,"riskLevel":risk},conn)
    return get_change(change_id)


def get_change(change_id: str):
    UUID(str(change_id))
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM nexus.change_requests WHERE change_id=%s", (change_id,))
            row = cur.fetchone()
            if not row:
                raise KeyError("Change request not found")
            change = dict(row)
            cur.execute("SELECT * FROM nexus.change_steps WHERE change_id=%s ORDER BY position", (change_id,))
            steps = [dict(r) for r in cur.fetchall()]
            cur.execute("SELECT * FROM nexus.change_approvals WHERE change_id=%s ORDER BY decided_at", (change_id,))
            approvals = [dict(r) for r in cur.fetchall()]
            cur.execute("SELECT * FROM nexus.change_execution_log WHERE change_id=%s ORDER BY occurred_at", (change_id,))
            logs = [dict(r) for r in cur.fetchall()]
    change["change_id"] = str(change["change_id"])
    if change.get("maintenance_window_id"):
        change["maintenance_window_id"] = str(change["maintenance_window_id"])
    change["steps"] = steps
    change["approvals"] = approvals
    change["logs"] = logs
    return change


def list_changes(status=None, limit=200):
    where = "WHERE status=%s" if status else ""
    args = (status,limit) if status else (limit,)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""SELECT * FROM nexus.change_requests {where}
                    ORDER BY created_at DESC LIMIT %s""", args
            )
            rows = [dict(r) for r in cur.fetchall()]
    for row in rows:
        row["change_id"] = str(row["change_id"])
        if row.get("maintenance_window_id"):
            row["maintenance_window_id"] = str(row["maintenance_window_id"])
    return rows


def approve(change_id: str, actor: str, reason=""):
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE nexus.change_requests
                   SET status='approved',approved_by=%s,approved_at=NOW(),updated_at=NOW()
                   WHERE change_id=%s AND status='pending-approval'
                   RETURNING change_id""",
                (actor,change_id),
            )
            if not cur.fetchone():
                raise ValueError("Change is not awaiting approval")
            cur.execute(
                """INSERT INTO nexus.change_approvals(change_id,decision,actor,reason)
                   VALUES(%s,'approved',%s,%s)""",(change_id,actor,reason)
            )
            append_log(change_id,"approved",actor,"Change request approved.",{"reason":reason},conn)
    return get_change(change_id)


def queue_execution(change_id: str, actor: str):
    change = get_change(change_id)
    if change["status"] not in {"approved","scheduled"}:
        raise ValueError("Change must be approved before execution")

    operation_id = f"change-{change_id}"
    with transaction() as conn:
        queue_available = operation_queue_available(conn)
        with conn.cursor() as cur:
            if queue_available:
                cur.execute(
                    """INSERT INTO nexus.operation_queue
                       (operation_id,action_name,target_type,target_id,asset_id,status,priority,
                        correlation_id,idempotency_key,triggered_by_type,triggered_by_id,
                        read_only,confirmation_required,confirmed,confirmed_by,confirmed_at,
                        input_data,summary,timeout_seconds,scheduled_for,queued_at)
                       VALUES(%s,%s,%s,%s,%s,'queued',%s,%s,%s,'operator',%s,
                              FALSE,TRUE,TRUE,%s,NOW(),%s,%s,300,NOW(),NOW())
                       ON CONFLICT(operation_id) DO NOTHING""",
                    (
                        operation_id,change["capability"],change["target_type"],change["target_id"],
                        change.get("asset_id"),25 if change["risk_level"] in {"high","critical"} else 50,
                        change["correlation_id"],f"change:{change_id}",actor,actor,
                        Jsonb({"changeId":change_id,"parameters":change.get("parameters") or {}}),
                        f"{change['change_number']} - {change['title']}",
                    ),
                )
                new_status = "executing"
                event_type = "execution-queued"
                message = "Controlled operation queued for the shared Operations Engine."
                details = {"operationId":operation_id, "queueAvailable": True}
            else:
                operation_id = None
                new_status = "approved"
                event_type = "execution-deferred"
                message = "Change is approved, but the shared Operations Queue is not installed yet."
                details = {"operationId": None, "queueAvailable": False}

            cur.execute(
                """UPDATE nexus.change_requests
                   SET status=%s,operation_id=%s,
                       started_at=CASE WHEN %s='executing' THEN NOW() ELSE started_at END,
                       updated_at=NOW()
                   WHERE change_id=%s""",
                (new_status,operation_id,new_status,change_id),
            )

            if queue_available:
                cur.execute(
                    """UPDATE nexus.change_steps SET status='succeeded',started_at=NOW(),completed_at=NOW()
                       WHERE change_id=%s AND position IN (1,2)""",(change_id,)
                )
                cur.execute(
                    """UPDATE nexus.change_steps SET status='running',started_at=NOW()
                       WHERE change_id=%s AND position=3""",(change_id,)
                )

            append_log(change_id,event_type,actor,message,details,conn)
    return get_change(change_id)


def terminal(change_id: str, status: str, actor: str, message: str, details=None):
    if status not in {"completed","failed","cancelled","rolled-back"}:
        raise ValueError("Unsupported terminal status")
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE nexus.change_requests
                   SET status=%s,completed_at=NOW(),updated_at=NOW(),
                       failure_reason=CASE WHEN %s='failed' THEN %s ELSE failure_reason END,
                       execution_result=%s
                   WHERE change_id=%s RETURNING change_id""",
                (status,status,message,Jsonb(details or {}),change_id),
            )
            if not cur.fetchone():
                raise KeyError("Change request not found")
            cur.execute(
                """UPDATE nexus.change_steps SET
                   status=CASE
                     WHEN %s='completed' AND position IN (3,4) THEN 'succeeded'
                     WHEN %s='failed' AND status='running' THEN 'failed'
                     ELSE status END,
                   completed_at=CASE WHEN status='running' THEN NOW() ELSE completed_at END
                   WHERE change_id=%s""",(status,status,change_id)
            )
            append_log(change_id,status,actor,message,details or {},conn)
    return get_change(change_id)


def create_rollback(change_id: str, actor: str):
    change = get_change(change_id)
    capability = change.get("rollback_capability") or ""
    if not capability:
        raise ValueError("This change has no rollback capability")

    with transaction() as conn:
        queue_available = operation_queue_available(conn)
        with conn.cursor() as cur:
            if queue_available:
                operation_id = f"rollback-{change_id}"
                cur.execute(
                    """INSERT INTO nexus.operation_queue
                       (operation_id,action_name,target_type,target_id,asset_id,status,priority,
                        correlation_id,idempotency_key,triggered_by_type,triggered_by_id,
                        read_only,confirmation_required,confirmed,confirmed_by,confirmed_at,
                        input_data,summary,timeout_seconds,scheduled_for,queued_at)
                       VALUES(%s,%s,%s,%s,%s,'queued',20,%s,%s,'operator',%s,
                              FALSE,TRUE,TRUE,%s,NOW(),%s,%s,300,NOW(),NOW())
                       ON CONFLICT(operation_id) DO NOTHING""",
                    (
                        operation_id,capability,change["target_type"],change["target_id"],
                        change.get("asset_id"),change["correlation_id"],f"rollback:{change_id}",
                        actor,actor,Jsonb({"changeId":change_id,"rollback":True}),
                        f"Rollback {change['change_number']} - {change['title']}",
                    ),
                )
                cur.execute(
                    """UPDATE nexus.change_requests SET status='rolling-back',
                       rollback_operation_id=%s,updated_at=NOW() WHERE change_id=%s""",
                    (operation_id,change_id),
                )
                append_log(change_id,"rollback-queued",actor,"Rollback operation queued.",
                           {"operationId":operation_id,"queueAvailable":True},conn)
            else:
                cur.execute(
                    """UPDATE nexus.change_requests SET status='rollback-pending',
                       rollback_operation_id=NULL,updated_at=NOW() WHERE change_id=%s""",
                    (change_id,),
                )
                append_log(change_id,"rollback-deferred",actor,
                           "Rollback is pending because the shared Operations Queue is not installed yet.",
                           {"operationId":None,"queueAvailable":False},conn)
    return get_change(change_id)


def history(change_id=None, limit=300):
    where = "WHERE l.change_id=%s" if change_id else ""
    args = (change_id,limit) if change_id else (limit,)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""SELECT l.*,c.change_number,c.title
                    FROM nexus.change_execution_log l
                    JOIN nexus.change_requests c ON c.change_id=l.change_id
                    {where}
                    ORDER BY l.occurred_at DESC LIMIT %s""",args
            )
            rows = [dict(r) for r in cur.fetchall()]
    for row in rows:
        row["change_id"] = str(row["change_id"])
    return rows
