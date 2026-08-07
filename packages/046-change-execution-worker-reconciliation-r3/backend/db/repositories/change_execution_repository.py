from __future__ import annotations

import socket
from datetime import timedelta
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from backend.db.connection import get_connection, transaction



def queue_available() -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('nexus.operation_queue') IS NOT NULL AS available")
            return bool(cur.fetchone()["available"])

def register_worker(worker_id: str, process_id: int, metadata=None):
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO nexus.change_execution_workers
                   (worker_id,hostname,process_id,status,last_heartbeat_at,metadata)
                   VALUES(%s,%s,%s,'idle',NOW(),%s)
                   ON CONFLICT(worker_id) DO UPDATE SET
                     hostname=EXCLUDED.hostname,process_id=EXCLUDED.process_id,
                     status='idle',last_heartbeat_at=NOW(),stopped_at=NULL,
                     metadata=EXCLUDED.metadata""",
                (worker_id, socket.gethostname(), process_id, Jsonb(metadata or {})),
            )


def heartbeat(worker_id: str, status="idle", operation_id=None):
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE nexus.change_execution_workers
                   SET status=%s,current_operation_id=%s,last_heartbeat_at=NOW()
                   WHERE worker_id=%s""",
                (status, operation_id, worker_id),
            )


def stop_worker(worker_id: str):
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE nexus.change_execution_workers
                   SET status='stopped',current_operation_id=NULL,
                       stopped_at=NOW(),last_heartbeat_at=NOW()
                   WHERE worker_id=%s""",
                (worker_id,),
            )


def claim_next(worker_id: str, lease_seconds=120):
    if not queue_available():
        return None
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT operation_id
                   FROM nexus.operation_queue
                   WHERE status IN ('pending','queued')
                     AND scheduled_for <= NOW()
                     AND (expires_at IS NULL OR expires_at > NOW())
                     AND cancellation_requested=FALSE
                   ORDER BY priority,scheduled_for,created_at
                   FOR UPDATE SKIP LOCKED
                   LIMIT 1"""
            )
            row = cur.fetchone()
            if not row:
                return None
            operation_id = row["operation_id"]
            cur.execute(
                """UPDATE nexus.operation_queue
                   SET status='running',lease_owner=%s,lease_acquired_at=NOW(),
                       lease_expires_at=NOW()+(%s || ' seconds')::interval,
                       heartbeat_at=NOW(),started_at=COALESCE(started_at,NOW()),
                       attempt_count=attempt_count+1,progress_percent=5,
                       current_step=1,updated_at=NOW()
                   WHERE operation_id=%s
                   RETURNING *""",
                (worker_id, int(lease_seconds), operation_id),
            )
            operation = dict(cur.fetchone())
            cur.execute(
                """INSERT INTO nexus.operation_queue_events
                   (operation_id,event_type,actor_type,actor_id,message,event_data)
                   VALUES(%s,'leased','worker',%s,'Operation claimed by execution worker.',%s)""",
                (operation_id, worker_id, Jsonb({"leaseSeconds":lease_seconds})),
            )
            return operation


def find_change_for_operation(operation_id: str):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT * FROM nexus.change_requests WHERE operation_id=%s",
                (operation_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def start_attempt(change, operation, worker_id: str):
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO nexus.change_execution_attempts
                   (change_id,operation_id,worker_id,attempt_number,status,
                    capability,target_type,target_id)
                   VALUES(%s,%s,%s,%s,'running',%s,%s,%s)
                   RETURNING attempt_id""",
                (
                    change["change_id"] if change else None,
                    operation["operation_id"], worker_id,
                    operation["attempt_count"], operation["action_name"],
                    operation["target_type"], operation["target_id"],
                ),
            )
            attempt_id = str(cur.fetchone()["attempt_id"])
            if change:
                cur.execute(
                    """UPDATE nexus.change_requests
                       SET status='executing',execution_worker_id=%s,updated_at=NOW()
                       WHERE change_id=%s""",
                    (worker_id, change["change_id"]),
                )
            return attempt_id


def finish_success(attempt_id: str, operation, change, result: dict[str, Any]):
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE nexus.change_execution_attempts
                   SET status='succeeded',completed_at=NOW(),duration_ms=%s,
                       exit_code=%s,timed_out=%s,transport=%s,stdout=%s,stderr=%s,
                       result_data=%s
                   WHERE attempt_id=%s""",
                (
                    result.get("durationMs"), result.get("exitCode"),
                    bool(result.get("timedOut")), result.get("transport",""),
                    result.get("stdout",""), result.get("stderr",""),
                    Jsonb(result), attempt_id,
                ),
            )
            cur.execute(
                """UPDATE nexus.operation_queue
                   SET status='succeeded',result_data=%s,summary=%s,
                       progress_percent=100,current_step=total_steps,
                       completed_at=NOW(),lease_owner='',lease_expires_at=NULL,
                       heartbeat_at=NOW(),updated_at=NOW()
                   WHERE operation_id=%s""",
                (Jsonb(result), "Controlled operation completed.", operation["operation_id"]),
            )
            if change:
                cur.execute(
                    """UPDATE nexus.change_requests
                       SET status='completed',verification_status='passed',
                           execution_result=%s,completed_at=NOW(),updated_at=NOW()
                       WHERE change_id=%s""",
                    (Jsonb(result), change["change_id"]),
                )
                cur.execute(
                    """UPDATE nexus.change_steps
                       SET status='succeeded',
                           started_at=COALESCE(started_at,NOW()),completed_at=NOW()
                       WHERE change_id=%s AND position IN (3,4)""",
                    (change["change_id"],),
                )
                cur.execute(
                    """INSERT INTO nexus.change_execution_log
                       (change_id,event_type,actor,message,details)
                       VALUES(%s,'execution-completed','change-execution-worker',
                              'Controlled operation and verification completed.',%s)""",
                    (change["change_id"], Jsonb({"operationId":operation["operation_id"],"result":result})),
                )


def finish_failure(attempt_id: str, operation, change, message: str, result=None):
    result = result or {}
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE nexus.change_execution_attempts
                   SET status='failed',completed_at=NOW(),duration_ms=%s,
                       exit_code=%s,timed_out=%s,transport=%s,stdout=%s,stderr=%s,
                       result_data=%s,error_message=%s
                   WHERE attempt_id=%s""",
                (
                    result.get("durationMs"), result.get("exitCode"),
                    bool(result.get("timedOut")), result.get("transport",""),
                    result.get("stdout",""), result.get("stderr",""),
                    Jsonb(result), message, attempt_id,
                ),
            )
            cur.execute(
                """UPDATE nexus.operation_queue
                   SET status='failed',result_data=%s,error_message=%s,
                       completed_at=NOW(),lease_owner='',lease_expires_at=NULL,
                       heartbeat_at=NOW(),updated_at=NOW()
                   WHERE operation_id=%s""",
                (Jsonb(result), message, operation["operation_id"]),
            )
            if change:
                cur.execute(
                    """UPDATE nexus.change_requests
                       SET status='failed',verification_status='failed',
                           failure_reason=%s,execution_result=%s,
                           completed_at=NOW(),updated_at=NOW()
                       WHERE change_id=%s""",
                    (message, Jsonb(result), change["change_id"]),
                )
                cur.execute(
                    """UPDATE nexus.change_steps
                       SET status='failed',completed_at=NOW(),error_message=%s
                       WHERE change_id=%s AND position=3""",
                    (message, change["change_id"]),
                )
                cur.execute(
                    """INSERT INTO nexus.change_execution_log
                       (change_id,event_type,actor,message,details)
                       VALUES(%s,'execution-failed','change-execution-worker',%s,%s)""",
                    (change["change_id"], message, Jsonb({"operationId":operation["operation_id"],"result":result})),
                )


def reconcile_stale(stale_seconds=180):
    if not queue_available():
        return []
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE nexus.operation_queue
                   SET status='queued',lease_owner='',lease_acquired_at=NULL,
                       lease_expires_at=NULL,heartbeat_at=NULL,
                       error_message='Recovered after stale worker lease.',
                       updated_at=NOW()
                   WHERE status='running'
                     AND COALESCE(lease_expires_at,heartbeat_at,started_at)
                         < NOW()-(%s || ' seconds')::interval
                   RETURNING operation_id""",
                (int(stale_seconds),),
            )
            return [r["operation_id"] for r in cur.fetchall()]


def status():
    available = queue_available()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT worker_id,hostname,process_id,status,current_operation_id,
                                  last_heartbeat_at,started_at,stopped_at,metadata
                           FROM nexus.change_execution_workers
                           ORDER BY last_heartbeat_at DESC LIMIT 50""")
            workers = [dict(r) for r in cur.fetchall()]
            queue = []
            if available:
                cur.execute("""SELECT status,COUNT(*) AS count
                               FROM nexus.operation_queue GROUP BY status ORDER BY status""")
                queue = [dict(r) for r in cur.fetchall()]
    return {"queueAvailable":available,"workers":workers,"queue":queue}


def history(limit=100):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT * FROM nexus.change_execution_attempts
                   ORDER BY started_at DESC LIMIT %s""",
                (int(limit),),
            )
            return [dict(r) for r in cur.fetchall()]
