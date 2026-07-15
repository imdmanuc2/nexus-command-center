"""Automatic Nexus Platform inventory synchronization and stale-state cleanup."""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any

from backend.db.connection import transaction
from scripts.sync_platform_inventory import main as sync_inventory


LOGGER = logging.getLogger("nexus.platform-sync")


def _stale_seconds() -> int:
    return max(
        60,
        int(os.getenv("NEXUS_PLATFORM_STALE_SECONDS", "300")),
    )


def reconcile_stale_state(
    *,
    stale_seconds: int,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Mark workers, workloads, pools, and relationships stale when unseen."""

    result: dict[str, Any] = {
        "staleSeconds": stale_seconds,
        "dryRun": dry_run,
        "workersMarkedOffline": 0,
        "workloadsMarkedOffline": 0,
        "poolsMarkedOffline": 0,
        "relationshipsMarkedInactive": 0,
    }

    with transaction() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT worker_id
                FROM nexus.workers
                WHERE last_seen_at < NOW() - (%s * INTERVAL '1 second')
                  AND LOWER(COALESCE(status, '')) NOT IN (
                      'offline',
                      'stale',
                      'down'
                  )
                """,
                (stale_seconds,),
            )
            stale_worker_ids = [
                row["worker_id"]
                for row in cursor.fetchall()
            ]

            if stale_worker_ids:
                cursor.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM nexus.workloads
                    WHERE worker_id = ANY(%s)
                      AND LOWER(COALESCE(status, '')) NOT IN (
                          'offline',
                          'stale',
                          'stopped'
                      )
                    """,
                    (stale_worker_ids,),
                )
                result["workloadsMarkedOffline"] = int(
                    cursor.fetchone()["count"]
                )

                cursor.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM nexus.relationships
                    WHERE source_type = 'worker'
                      AND source_id = ANY(%s)
                      AND LOWER(COALESCE(status, 'active')) = 'active'
                    """,
                    (stale_worker_ids,),
                )
                result["relationshipsMarkedInactive"] = int(
                    cursor.fetchone()["count"]
                )

            result["workersMarkedOffline"] = len(stale_worker_ids)

            cursor.execute(
                """
                SELECT COUNT(*) AS count
                FROM nexus.pools
                WHERE last_seen_at < NOW() - (%s * INTERVAL '1 second')
                  AND LOWER(COALESCE(status, '')) NOT IN (
                      'offline',
                      'stale',
                      'down'
                  )
                """,
                (stale_seconds,),
            )
            result["poolsMarkedOffline"] = int(
                cursor.fetchone()["count"]
            )

            if dry_run:
                connection.rollback()
                return result

            if stale_worker_ids:
                cursor.execute(
                    """
                    UPDATE nexus.workers
                    SET
                        status = 'offline',
                        reconciliation_status = 'stale',
                        updated_at = NOW()
                    WHERE worker_id = ANY(%s)
                    """,
                    (stale_worker_ids,),
                )

                cursor.execute(
                    """
                    UPDATE nexus.workloads
                    SET
                        status = 'offline',
                        updated_at = NOW()
                    WHERE worker_id = ANY(%s)
                      AND LOWER(COALESCE(status, '')) NOT IN (
                          'stopped',
                          'retired'
                      )
                    """,
                    (stale_worker_ids,),
                )

                cursor.execute(
                    """
                    UPDATE nexus.relationships
                    SET
                        status = 'inactive',
                        updated_at = NOW()
                    WHERE source_type = 'worker'
                      AND source_id = ANY(%s)
                      AND LOWER(COALESCE(status, 'active')) = 'active'
                    """,
                    (stale_worker_ids,),
                )

            cursor.execute(
                """
                UPDATE nexus.pools
                SET
                    status = 'offline',
                    updated_at = NOW()
                WHERE last_seen_at < NOW() - (%s * INTERVAL '1 second')
                  AND LOWER(COALESCE(status, '')) NOT IN (
                      'offline',
                      'stale',
                      'down'
                  )
                """,
                (stale_seconds,),
            )

    return result


def run_once(
    *,
    stale_seconds: int,
    dry_run: bool = False,
) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc)

    LOGGER.info("Starting Nexus Platform synchronization.")

    sync_exit = sync_inventory()
    if sync_exit not in (None, 0):
        raise RuntimeError(
            f"Platform inventory sync returned {sync_exit}."
        )

    stale = reconcile_stale_state(
        stale_seconds=stale_seconds,
        dry_run=dry_run,
    )

    completed_at = datetime.now(timezone.utc)

    return {
        "status": "ok",
        "source": "nexus-platform-sync-job",
        "startedAt": started_at.isoformat(),
        "completedAt": completed_at.isoformat(),
        "durationSeconds": round(
            (completed_at - started_at).total_seconds(),
            3,
        ),
        "staleReconciliation": stale,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Synchronize live Nexus inventory into PostgreSQL and "
            "mark stale platform records offline."
        )
    )
    parser.add_argument(
        "--stale-seconds",
        type=int,
        default=_stale_seconds(),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
    )
    return parser.parse_args()


def main() -> int:
    logging.basicConfig(
        level=os.getenv("NEXUS_PLATFORM_SYNC_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    args = parse_args()

    try:
        result = run_once(
            stale_seconds=max(60, args.stale_seconds),
            dry_run=args.dry_run,
        )
    except Exception:
        LOGGER.exception("Nexus Platform synchronization failed.")
        return 1

    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
