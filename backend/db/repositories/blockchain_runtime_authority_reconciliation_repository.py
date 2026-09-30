from __future__ import annotations

from datetime import datetime
from typing import Any

from backend.db.connection import get_connection, transaction


_ENGINE_NAME = "blockchain-runtime-authority-reconciliation"
_PHASE_DATED = "dated"
_PHASE_NULL = "null"
_VALID_PHASES = {
    _PHASE_DATED,
    _PHASE_NULL,
}


def initial_state() -> dict[str, Any]:
    return {
        "engine_name": _ENGINE_NAME,
        "phase": _PHASE_DATED,
        "after_completed_at": None,
        "after_operation_id": None,
    }


# Stable two-key PostgreSQL advisory-lock namespace for this reconciliation
# engine. Session ownership is intentional: the lock must span repository
# calls that use their own independent transactions.
_RECONCILIATION_LOCK_NAMESPACE = 0x5345594D
_RECONCILIATION_LOCK_KEY = 0x41555448


def try_acquire_reconciliation_lock():
    connection = get_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT pg_try_advisory_lock(%s, %s) AS acquired
                """,
                (
                    _RECONCILIATION_LOCK_NAMESPACE,
                    _RECONCILIATION_LOCK_KEY,
                ),
            )
            row = cursor.fetchone()

        acquired = bool(row and row["acquired"])

        if not acquired:
            connection.close()
            return None

        return connection
    except Exception:
        connection.close()
        raise


def release_reconciliation_lock(connection) -> None:
    if connection is None:
        return

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT pg_advisory_unlock(%s, %s) AS released
                """,
                (
                    _RECONCILIATION_LOCK_NAMESPACE,
                    _RECONCILIATION_LOCK_KEY,
                ),
            )
            cursor.fetchone()
    finally:
        connection.close()


def get_state() -> dict[str, Any]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    engine_name,
                    phase,
                    after_completed_at,
                    after_operation_id
                FROM nexus.blockchain_runtime_authority_reconciliation_state
                WHERE engine_name = %s
                """,
                (_ENGINE_NAME,),
            )
            row = cursor.fetchone()

    return dict(row) if row else initial_state()


def update_state(
    *,
    phase: str,
    after_completed_at: datetime | None = None,
    after_operation_id: str | None = None,
) -> None:
    phase = str(phase or "").strip()

    if phase not in _VALID_PHASES:
        raise ValueError(
            "Authority reconciliation phase must be dated or null"
        )

    operation_id = str(after_operation_id or "").strip() or None

    if phase == _PHASE_DATED:
        if (after_completed_at is None) != (operation_id is None):
            raise ValueError(
                "Dated authority reconciliation cursor requires both "
                "completed_at and operation_id, or neither"
            )
    else:
        if after_completed_at is not None:
            raise ValueError(
                "NULL authority reconciliation phase cannot persist "
                "completed_at"
            )

    with transaction() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO nexus.blockchain_runtime_authority_reconciliation_state (
                    engine_name,
                    phase,
                    after_completed_at,
                    after_operation_id,
                    updated_at
                )
                VALUES (
                    %s,
                    %s,
                    %s,
                    %s,
                    NOW()
                )
                ON CONFLICT (engine_name)
                DO UPDATE SET
                    phase = EXCLUDED.phase,
                    after_completed_at = EXCLUDED.after_completed_at,
                    after_operation_id = EXCLUDED.after_operation_id,
                    updated_at = NOW()
                """,
                (
                    _ENGINE_NAME,
                    phase,
                    after_completed_at,
                    operation_id,
                ),
            )


def reset_state() -> None:
    update_state(
        phase=_PHASE_DATED,
        after_completed_at=None,
        after_operation_id=None,
    )
