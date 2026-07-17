
from __future__ import annotations

from typing import Any

from backend.db.connection import transaction


def update_topology_reconciliation_state(
    *,
    status: str,
    written: int,
    deactivated: int,
    error: str = "",
) -> None:
    with transaction() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO nexus.topology_reconciliation_state (
                    reconciler_name,
                    last_started_at,
                    last_completed_at,
                    last_status,
                    last_error,
                    relationships_written,
                    relationships_deactivated,
                    updated_at
                )
                VALUES (
                    'live-postgresql-topology',
                    NOW(),
                    NOW(),
                    %s,
                    %s,
                    %s,
                    %s,
                    NOW()
                )
                ON CONFLICT (reconciler_name)
                DO UPDATE SET
                    last_started_at = NOW(),
                    last_completed_at = NOW(),
                    last_status = EXCLUDED.last_status,
                    last_error = EXCLUDED.last_error,
                    relationships_written =
                        EXCLUDED.relationships_written,
                    relationships_deactivated =
                        EXCLUDED.relationships_deactivated,
                    updated_at = NOW()
                """,
                (
                    status,
                    error,
                    written,
                    deactivated,
                ),
            )
