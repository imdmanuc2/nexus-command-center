from __future__ import annotations

from backend.core.operation_execution_control import (
    OperationCancellationRequested,
    OperationLeaseLost,
)


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


def _attempt_limit_column(conn) -> str:
    """Resolve the supported operation_queue attempt-limit column.

    Migration 004 created `maximum_attempts`; migration 035's fallback
    queue definition created `max_attempts`. Existing Nexus deployments
    may therefore legitimately contain either spelling.
    """
    with conn.cursor() as cur:
        cur.execute(
            """SELECT column_name
               FROM information_schema.columns
               WHERE table_schema='nexus'
                 AND table_name='operation_queue'
                 AND column_name IN ('maximum_attempts','max_attempts')"""
        )
        columns = {row["column_name"] for row in cur.fetchall()}

    if "maximum_attempts" in columns:
        return "maximum_attempts"
    if "max_attempts" in columns:
        return "max_attempts"

    raise RuntimeError(
        "Operations Queue attempt-limit column is unavailable"
    )

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
        attempt_limit_column = _attempt_limit_column(conn)
        with conn.cursor() as cur:
            cur.execute(
                f"""SELECT operation_id
                   FROM nexus.operation_queue
                   WHERE status IN ('pending','queued')
                     AND scheduled_for <= NOW()
                     AND (expires_at IS NULL OR expires_at > NOW())
                     AND cancellation_requested=FALSE
                     AND attempt_count < {attempt_limit_column}
                   ORDER BY priority,scheduled_for,created_at
                   FOR UPDATE SKIP LOCKED
                   LIMIT 1"""
            )
            row = cur.fetchone()
            if not row:
                return None
            operation_id = row["operation_id"]
            cur.execute(
                f"""UPDATE nexus.operation_queue
                   SET status='running',lease_owner=%s,lease_acquired_at=NOW(),
                       lease_expires_at=NOW()+(%s || ' seconds')::interval,
                       heartbeat_at=NOW(),started_at=COALESCE(started_at,NOW()),
                       attempt_count=attempt_count+1,progress_percent=5,
                       current_step=1,updated_at=NOW()
                   WHERE operation_id=%s
                     AND attempt_count < {attempt_limit_column}
                   RETURNING *""",
                (worker_id, int(lease_seconds), operation_id),
            )
            claimed = cur.fetchone()
            if not claimed:
                return None
            operation = dict(claimed)
            cur.execute(
                """INSERT INTO nexus.operation_queue_events
                   (operation_id,event_type,actor_type,actor_id,message,event_data)
                   VALUES(%s,'leased','worker',%s,'Operation claimed by execution worker.',%s)""",
                (
                    operation_id,
                    worker_id,
                    Jsonb({"leaseSeconds": lease_seconds}),
                ),
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



def _claim_terminal_authority(
    cur,
    operation_id: str,
    worker_id: str,
    terminal_status: str,
    *,
    result=None,
    summary=None,
    error_message=None,
):
    operation_id = str(operation_id or "").strip()
    worker_id = str(worker_id or "").strip()

    if not operation_id:
        raise ValueError("operation_id is required")
    if not worker_id:
        raise ValueError("worker_id is required")

    if terminal_status not in {
        "succeeded",
        "failed",
        "cancelled",
    }:
        raise ValueError(
            "unsupported terminal operation status"
        )

    result = result or {}

    if terminal_status == "succeeded":
        cur.execute(
            """UPDATE nexus.operation_queue
               SET status='succeeded',
                   result_data=%s,
                   summary=%s,
                   error_message=NULL,
                   progress_percent=100,
                   current_step=total_steps,
                   completed_at=NOW(),
                   lease_owner='',
                   lease_expires_at=NULL,
                   heartbeat_at=NOW(),
                   updated_at=NOW()
               WHERE operation_id=%s
                 AND status='running'
                 AND lease_owner=%s
                 AND cancellation_requested=FALSE
               RETURNING operation_id""",
            (
                Jsonb(result),
                summary,
                operation_id,
                worker_id,
            ),
        )
    elif terminal_status == "failed":
        cur.execute(
            """UPDATE nexus.operation_queue
               SET status='failed',
                   result_data=%s,
                   error_message=%s,
                   completed_at=NOW(),
                   lease_owner='',
                   lease_expires_at=NULL,
                   heartbeat_at=NOW(),
                   updated_at=NOW()
               WHERE operation_id=%s
                 AND status='running'
                 AND lease_owner=%s
                 AND cancellation_requested=FALSE
               RETURNING operation_id""",
            (
                Jsonb(result),
                error_message,
                operation_id,
                worker_id,
            ),
        )
    else:
        cur.execute(
            """UPDATE nexus.operation_queue
               SET status='cancelled',
                   result_data=%s,
                   summary=%s,
                   error_message=NULL,
                   completed_at=NOW(),
                   cancelled_at=COALESCE(cancelled_at,NOW()),
                   lease_owner='',
                   lease_expires_at=NULL,
                   heartbeat_at=NOW(),
                   updated_at=NOW()
               WHERE operation_id=%s
                 AND status='running'
                 AND lease_owner=%s
                 AND cancellation_requested=TRUE
               RETURNING operation_id""",
            (
                Jsonb(result),
                summary,
                operation_id,
                worker_id,
            ),
        )

    owned = cur.fetchone()

    if not owned:
        raise OperationLeaseLost(
            "Operation terminal finalization lost ownership"
        )


def finish_success(
    attempt_id: str,
    operation,
    change,
    result: dict[str, Any],
    worker_id: str,
):
    with transaction() as conn:
        with conn.cursor() as cur:
            _claim_terminal_authority(
                cur,
                operation["operation_id"],
                worker_id,
                "succeeded",
                result=result,
                summary="Controlled operation completed.",
            )

            cur.execute(
                """UPDATE nexus.change_execution_attempts
                   SET status='succeeded',
                       completed_at=NOW(),
                       duration_ms=%s,
                       exit_code=%s,
                       timed_out=%s,
                       transport=%s,
                       stdout=%s,
                       stderr=%s,
                       result_data=%s
                   WHERE attempt_id=%s
                     AND operation_id=%s
                     AND worker_id=%s
                     AND status='running'""",
                (
                    result.get("durationMs"),
                    result.get("exitCode"),
                    bool(result.get("timedOut")),
                    result.get("transport", ""),
                    result.get("stdout", ""),
                    result.get("stderr", ""),
                    Jsonb(result),
                    attempt_id,
                    operation["operation_id"],
                    worker_id,
                ),
            )

            if change:
                cur.execute(
                    """UPDATE nexus.change_requests
                       SET status='completed',
                           verification_status='passed',
                           execution_result=%s,
                           execution_worker_id='',
                           completed_at=NOW(),
                           updated_at=NOW()
                       WHERE change_id=%s
                         AND operation_id=%s
                         AND status='executing'""",
                    (
                        Jsonb(result),
                        change["change_id"],
                        operation["operation_id"],
                    ),
                )

                cur.execute(
                    """UPDATE nexus.change_steps
                       SET status='succeeded',
                           started_at=COALESCE(started_at,NOW()),
                           completed_at=NOW()
                       WHERE change_id=%s
                         AND position IN (3,4)""",
                    (change["change_id"],),
                )

                cur.execute(
                    """INSERT INTO nexus.change_execution_log
                       (change_id,event_type,actor,message,details)
                       VALUES(
                           %s,
                           'execution-completed',
                           'change-execution-worker',
                           'Controlled operation and verification completed.',
                           %s
                       )""",
                    (
                        change["change_id"],
                        Jsonb({
                            "operationId":
                                operation["operation_id"],
                            "result": result,
                        }),
                    ),
                )


def finish_failure(
    attempt_id: str,
    operation,
    change,
    message: str,
    result,
    worker_id: str,
):
    result = result or {}

    with transaction() as conn:
        with conn.cursor() as cur:
            _claim_terminal_authority(
                cur,
                operation["operation_id"],
                worker_id,
                "failed",
                result=result,
                error_message=message,
            )

            cur.execute(
                """UPDATE nexus.change_execution_attempts
                   SET status='failed',
                       completed_at=NOW(),
                       duration_ms=%s,
                       exit_code=%s,
                       timed_out=%s,
                       transport=%s,
                       stdout=%s,
                       stderr=%s,
                       result_data=%s,
                       error_message=%s
                   WHERE attempt_id=%s
                     AND operation_id=%s
                     AND worker_id=%s
                     AND status='running'""",
                (
                    result.get("durationMs"),
                    result.get("exitCode"),
                    bool(result.get("timedOut")),
                    result.get("transport", ""),
                    result.get("stdout", ""),
                    result.get("stderr", ""),
                    Jsonb(result),
                    message,
                    attempt_id,
                    operation["operation_id"],
                    worker_id,
                ),
            )

            if change:
                cur.execute(
                    """UPDATE nexus.change_requests
                       SET status='failed',
                           verification_status='failed',
                           execution_worker_id='',
                           failure_reason=%s,
                           execution_result=%s,
                           completed_at=NOW(),
                           updated_at=NOW()
                       WHERE change_id=%s
                         AND operation_id=%s
                         AND status='executing'""",
                    (
                        message,
                        Jsonb(result),
                        change["change_id"],
                        operation["operation_id"],
                    ),
                )

                cur.execute(
                    """UPDATE nexus.change_steps
                       SET status='failed',
                           completed_at=NOW(),
                           error_message=%s
                       WHERE change_id=%s
                         AND position=3
                         AND status IN ('pending','running')""",
                    (
                        message,
                        change["change_id"],
                    ),
                )

                cur.execute(
                    """INSERT INTO nexus.change_execution_log
                       (change_id,event_type,actor,message,details)
                       VALUES(
                           %s,
                           'execution-failed',
                           'change-execution-worker',
                           %s,
                           %s
                       )""",
                    (
                        change["change_id"],
                        message,
                        Jsonb({
                            "operationId":
                                operation["operation_id"],
                            "result": result,
                        }),
                    ),
                )


def finish_cancelled(
    attempt_id: str,
    operation,
    change,
    worker_id: str,
    message: str = "Controlled operation cancelled.",
):
    result = {
        "status": "cancelled",
        "operationId": operation["operation_id"],
        "message": message,
    }

    with transaction() as conn:
        with conn.cursor() as cur:
            _claim_terminal_authority(
                cur,
                operation["operation_id"],
                worker_id,
                "cancelled",
                result=result,
                summary=message,
            )

            cur.execute(
                """UPDATE nexus.change_execution_attempts
                   SET status='failed',
                       completed_at=NOW(),
                       result_data=%s,
                       error_message=%s
                   WHERE attempt_id=%s
                     AND operation_id=%s
                     AND worker_id=%s
                     AND status='running'""",
                (
                    Jsonb(result),
                    message,
                    attempt_id,
                    operation["operation_id"],
                    worker_id,
                ),
            )

            if change:
                cur.execute(
                    """UPDATE nexus.change_requests
                       SET status='cancelled',
                           execution_worker_id='',
                           execution_result=%s,
                           completed_at=NOW(),
                           updated_at=NOW()
                       WHERE change_id=%s
                         AND operation_id=%s
                         AND status='executing'""",
                    (
                        Jsonb(result),
                        change["change_id"],
                        operation["operation_id"],
                    ),
                )

                cur.execute(
                    """UPDATE nexus.change_steps
                       SET status='skipped',
                           completed_at=NOW(),
                           error_message=%s
                       WHERE change_id=%s
                         AND status IN ('pending','running')""",
                    (
                        message,
                        change["change_id"],
                    ),
                )

                cur.execute(
                    """INSERT INTO nexus.change_execution_log
                       (change_id,event_type,actor,message,details)
                       VALUES(
                           %s,
                           'execution-cancelled',
                           'change-execution-worker',
                           %s,
                           %s
                       )""",
                    (
                        change["change_id"],
                        message,
                        Jsonb({
                            "operationId":
                                operation["operation_id"],
                            "reason": "cancellation-requested",
                        }),
                    ),
                )

def reconcile_stale(stale_seconds=180):
    if not queue_available():
        return []

    stale_seconds = int(stale_seconds)
    if stale_seconds < 1:
        raise ValueError("stale_seconds must be positive")

    recovered = []
    failed = []

    with transaction() as conn:
        attempt_limit_column = _attempt_limit_column(conn)
        with conn.cursor() as cur:

            cur.execute(
                f"""UPDATE nexus.operation_queue
                   SET status='queued',lease_owner='',lease_acquired_at=NULL,
                       lease_expires_at=NULL,heartbeat_at=NULL,
                       error_message='Recovered after stale worker lease; retry permitted.',
                       updated_at=NOW()
                   WHERE status='running'
                     AND attempt_count < {attempt_limit_column}
                     AND COALESCE(lease_expires_at,heartbeat_at,started_at)
                         < NOW()-(%s || ' seconds')::interval
                   RETURNING operation_id""",
                (stale_seconds,),
            )
            recovered = [str(row["operation_id"]) for row in cur.fetchall()]

            if recovered:
                cur.execute(
                    """UPDATE nexus.change_execution_attempts
                       SET status='failed',completed_at=NOW(),
                           error_message='Execution attempt abandoned after stale worker lease.'
                       WHERE operation_id = ANY(%s)
                         AND status='running'""",
                    (recovered,),
                )
                cur.execute(
                    """UPDATE nexus.change_requests
                       SET execution_worker_id='',updated_at=NOW()
                       WHERE operation_id = ANY(%s)
                         AND status='executing'""",
                    (recovered,),
                )

            cur.execute(
                f"""UPDATE nexus.operation_queue
                   SET status='failed',lease_owner='',lease_acquired_at=NULL,
                       lease_expires_at=NULL,heartbeat_at=NULL,
                       error_message='Stale worker lease exhausted operation retry budget.',
                       completed_at=COALESCE(completed_at,NOW()),
                       updated_at=NOW()
                   WHERE status='running'
                     AND attempt_count >= {attempt_limit_column}
                     AND COALESCE(lease_expires_at,heartbeat_at,started_at)
                         < NOW()-(%s || ' seconds')::interval
                   RETURNING operation_id""",
                (stale_seconds,),
            )
            failed = [str(row["operation_id"]) for row in cur.fetchall()]

            if failed:
                cur.execute(
                    """UPDATE nexus.change_execution_attempts
                       SET status='failed',completed_at=NOW(),
                           error_message='Execution attempt abandoned after stale worker lease; retry budget exhausted.'
                       WHERE operation_id = ANY(%s)
                         AND status='running'""",
                    (failed,),
                )
                cur.execute(
                    """UPDATE nexus.change_requests
                       SET status='failed',
                           execution_worker_id='',
                           verification_status='failed',
                           completed_at=COALESCE(completed_at,NOW()),
                           failure_reason='Stale worker lease exhausted operation retry budget.',
                           updated_at=NOW()
                       WHERE operation_id = ANY(%s)
                         AND status='executing'""",
                    (failed,),
                )
                cur.execute(
                    """UPDATE nexus.change_steps
                       SET status='failed',
                           completed_at=COALESCE(completed_at,NOW())
                       WHERE change_id IN (
                           SELECT change_id
                           FROM nexus.change_requests
                           WHERE operation_id = ANY(%s)
                       )
                         AND status='running'""",
                    (failed,),
                )
                cur.execute(
                    """INSERT INTO nexus.change_execution_log
                       (change_id,event_type,actor,message,details)
                       SELECT change_id,'execution-failed','change-execution-worker',
                              'Controlled operation failed after stale worker lease exhausted retry budget.',
                              %s
                       FROM nexus.change_requests
                       WHERE operation_id = ANY(%s)""",
                    (
                        Jsonb({
                            "reason": "stale-worker-lease",
                            "retryBudgetExhausted": True,
                        }),
                        failed,
                    ),
                )

    return {
        "recovered": recovered,
        "failed": failed,
    }

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


def checkpoint_operation(
    operation_id: str,
    worker_id: str,
    current_step: int,
    total_steps: int,
    lease_seconds: int = 120,
):
    operation_id = str(operation_id or "").strip()
    worker_id = str(worker_id or "").strip()

    if not operation_id:
        raise ValueError("operation_id is required")
    if not worker_id:
        raise ValueError("worker_id is required")

    current_step = int(current_step)
    total_steps = int(total_steps)
    lease_seconds = int(lease_seconds)

    if total_steps < 1:
        raise ValueError("total_steps must be positive")
    if current_step < 1 or current_step > total_steps:
        raise ValueError(
            "current_step must be within total_steps"
        )
    if lease_seconds < 1:
        raise ValueError("lease_seconds must be positive")

    progress_percent = max(
        5,
        min(
            95,
            int(
                ((current_step - 1) * 100)
                / total_steps
            ),
        ),
    )

    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT operation_id,status,lease_owner,
                          cancellation_requested
                   FROM nexus.operation_queue
                   WHERE operation_id=%s
                   FOR UPDATE""",
                (operation_id,),
            )
            row = cur.fetchone()

            if not row:
                raise RuntimeError(
                    "Operation no longer exists"
                )

            operation = dict(row)

            if operation.get("status") != "running":
                raise RuntimeError(
                    "Operation is no longer running"
                )

            if operation.get("lease_owner") != worker_id:
                raise OperationLeaseLost(
                    "Operation lease ownership was lost"
                )

            if bool(
                operation.get(
                    "cancellation_requested"
                )
            ):
                raise OperationCancellationRequested(
                    "Operation cancellation requested"
                )

            cur.execute(
                """UPDATE nexus.operation_queue
                   SET lease_expires_at=
                         NOW()+(%s || ' seconds')::interval,
                       heartbeat_at=NOW(),
                       current_step=%s,
                       total_steps=%s,
                       progress_percent=%s,
                       updated_at=NOW()
                   WHERE operation_id=%s
                     AND status='running'
                     AND lease_owner=%s
                     AND cancellation_requested=FALSE
                   RETURNING operation_id,status,
                             lease_owner,current_step,
                             total_steps,progress_percent,
                             lease_expires_at,
                             heartbeat_at""",
                (
                    lease_seconds,
                    current_step,
                    total_steps,
                    progress_percent,
                    operation_id,
                    worker_id,
                ),
            )

            updated = cur.fetchone()

            if not updated:
                raise OperationLeaseLost(
                    "Operation checkpoint lost ownership"
                )

            return dict(updated)


def list_successful_blockchain_install_results(
    limit: int = 100,
    *,
    after_completed_at=None,
    after_operation_id: str | None = None,
    include_null_completed_at: bool = False,
):
    """Return bounded durable successful blockchain.install results.

    These rows are execution evidence only. Callers must replay the
    persisted result through the canonical authority projection service;
    they must never re-execute the operation or target lifecycle.

    Dated rows are traversed newest-first using the stable composite
    (completed_at, operation_id) key. Legacy rows without completed_at
    are traversed separately by operation_id so they cannot be skipped
    or pin dated pagination.
    """
    limit = int(limit)

    if limit < 1:
        raise ValueError("limit must be positive")

    limit = min(limit, 500)

    if include_null_completed_at:
        if after_completed_at is not None:
            raise ValueError(
                "after_completed_at is invalid for NULL completed_at phase"
            )
    else:
        if (
            after_completed_at is None
            and after_operation_id is not None
        ):
            raise ValueError(
                "after_operation_id requires after_completed_at"
            )

        if (
            after_completed_at is not None
            and not after_operation_id
        ):
            raise ValueError(
                "after_completed_at requires after_operation_id"
            )

    if not queue_available():
        return []

    where = [
        "action_name = 'blockchain.install'",
        "status = 'succeeded'",
        "jsonb_typeof(result_data) = 'object'",
        "result_data <> '{}'::jsonb",
        "BTRIM(operation_id) <> ''",
    ]

    params = []

    if include_null_completed_at:
        where.append("completed_at IS NULL")

        if after_operation_id:
            where.append("operation_id < %s")
            params.append(after_operation_id)

        order_by = "operation_id DESC"
    else:
        where.append("completed_at IS NOT NULL")

        if after_completed_at is not None:
            where.append(
                "(completed_at, operation_id) < (%s, %s)"
            )
            params.extend(
                [
                    after_completed_at,
                    after_operation_id,
                ]
            )

        order_by = "completed_at DESC, operation_id DESC"

    params.append(limit)

    sql = f"""
        SELECT
            operation_id,
            action_name,
            target_id,
            asset_id,
            correlation_id,
            confirmed_by,
            result_data,
            completed_at
        FROM nexus.operation_queue
        WHERE {' AND '.join(where)}
        ORDER BY {order_by}
        LIMIT %s
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                sql,
                tuple(params),
            )

            return [
                dict(row)
                for row in cur.fetchall()
            ]
