from __future__ import annotations

import argparse
import json
from typing import Any

from backend.db.connection import get_connection


CONFIRMATION = "CONSOLIDATE-SEYMOUR-RUNTIME-IDENTITIES"


def _rows(cursor) -> list[dict[str, Any]]:
    return [dict(row) for row in cursor.fetchall()]


def _canonical_assets(
    cursor,
    *,
    manager_asset_id: str,
    bch_asset_id: str,
) -> None:
    cursor.execute(
        """
        SELECT asset_id, asset_type, coin
        FROM nexus.assets
        WHERE asset_id IN (%s, %s)
        """,
        (manager_asset_id, bch_asset_id),
    )

    rows = {
        row["asset_id"]: row
        for row in cursor.fetchall()
    }

    manager = rows.get(manager_asset_id)
    bch = rows.get(bch_asset_id)

    if not manager:
        raise RuntimeError(
            f"Canonical Manager asset does not exist: "
            f"{manager_asset_id}"
        )

    if manager["asset_type"] != "blockchain-manager":
        raise RuntimeError(
            "Canonical Manager asset has unexpected type: "
            f"{manager['asset_type']}"
        )

    if not bch:
        raise RuntimeError(
            f"Canonical BCH asset does not exist: "
            f"{bch_asset_id}"
        )

    if (
        bch["asset_type"] != "blockchain-node"
        or bch["coin"] != "BCH"
    ):
        raise RuntimeError(
            "Canonical BCH asset does not identify a BCH "
            "blockchain-node."
        )


def _stale_assets(
    cursor,
    *,
    manager_asset_id: str,
    bch_asset_id: str,
) -> tuple[list[str], list[str]]:
    cursor.execute(
        """
        SELECT asset_id
        FROM nexus.assets
        WHERE asset_type = 'blockchain-manager'
          AND asset_id <> %s
        ORDER BY asset_id
        """,
        (manager_asset_id,),
    )

    stale_managers = [
        row["asset_id"]
        for row in cursor.fetchall()
    ]

    cursor.execute(
        """
        SELECT asset_id
        FROM nexus.assets
        WHERE asset_type = 'blockchain-node'
          AND coin = 'BCH'
          AND asset_id <> %s
        ORDER BY asset_id
        """,
        (bch_asset_id,),
    )

    stale_bch = [
        row["asset_id"]
        for row in cursor.fetchall()
    ]

    return stale_managers, stale_bch


def _count(
    cursor,
    statement: str,
    parameters: tuple[Any, ...],
) -> int:
    cursor.execute(statement, parameters)
    return int(cursor.fetchone()["count"])


def _unexpected_fk_references(
    cursor,
    stale_asset_ids: list[str],
) -> list[dict[str, Any]]:
    if not stale_asset_ids:
        return []

    allowed = {
        ("audit_events", "asset_id"),
        ("blockchain_nodes", "asset_id"),
    }

    cursor.execute(
        """
        SELECT
            tc.table_name,
            kcu.column_name,
            rc.delete_rule
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu
          ON tc.constraint_name = kcu.constraint_name
         AND tc.constraint_schema = kcu.constraint_schema
        JOIN information_schema.constraint_column_usage ccu
          ON tc.constraint_name = ccu.constraint_name
         AND tc.constraint_schema = ccu.constraint_schema
        JOIN information_schema.referential_constraints rc
          ON tc.constraint_name = rc.constraint_name
         AND tc.constraint_schema = rc.constraint_schema
        WHERE tc.constraint_type = 'FOREIGN KEY'
          AND tc.constraint_schema = 'nexus'
          AND ccu.table_schema = 'nexus'
          AND ccu.table_name = 'assets'
          AND ccu.column_name = 'asset_id'
        ORDER BY tc.table_name, kcu.column_name
        """
    )

    dependencies = _rows(cursor)
    unexpected: list[dict[str, Any]] = []

    from psycopg import sql

    for dependency in dependencies:
        table = dependency["table_name"]
        column = dependency["column_name"]

        if (table, column) in allowed:
            continue

        query = sql.SQL(
            """
            SELECT COUNT(*) AS count
            FROM nexus.{}
            WHERE {} = ANY(%s)
            """
        ).format(
            sql.Identifier(table),
            sql.Identifier(column),
        )

        cursor.execute(
            query,
            (stale_asset_ids,),
        )

        count = int(cursor.fetchone()["count"])

        if count:
            unexpected.append(
                {
                    **dependency,
                    "count": count,
                }
            )

    return unexpected


def build_plan(
    *,
    manager_asset_id: str,
    bch_asset_id: str,
) -> dict[str, Any]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            _canonical_assets(
                cursor,
                manager_asset_id=manager_asset_id,
                bch_asset_id=bch_asset_id,
            )

            stale_managers, stale_bch = _stale_assets(
                cursor,
                manager_asset_id=manager_asset_id,
                bch_asset_id=bch_asset_id,
            )

            stale_assets = stale_managers + stale_bch

            audit_events = (
                _count(
                    cursor,
                    """
                    SELECT COUNT(*) AS count
                    FROM nexus.audit_events
                    WHERE asset_id = ANY(%s)
                    """,
                    (stale_bch,),
                )
                if stale_bch
                else 0
            )

            metrics = (
                _count(
                    cursor,
                    """
                    SELECT COUNT(*) AS count
                    FROM nexus.current_metrics
                    WHERE subject_id = ANY(%s)
                    """,
                    (stale_bch,),
                )
                if stale_bch
                else 0
            )

            node_rows = (
                _count(
                    cursor,
                    """
                    SELECT COUNT(*) AS count
                    FROM nexus.blockchain_nodes
                    WHERE asset_id = ANY(%s)
                    """,
                    (stale_bch,),
                )
                if stale_bch
                else 0
            )

            if stale_assets:
                cursor.execute(
                    """
                    SELECT
                        relationship_id,
                        source_id,
                        relationship_type,
                        target_id,
                        source
                    FROM nexus.relationships
                    WHERE source_id = ANY(%s)
                       OR target_id = ANY(%s)
                    ORDER BY relationship_id
                    """,
                    (stale_assets, stale_assets),
                )

                relationships = _rows(cursor)
            else:
                relationships = []

            unexpected_relationships = [
                relationship
                for relationship in relationships
                if not (
                    relationship["relationship_type"] == "manages"
                    and relationship["source"]
                    == "seymour-registration"
                    and relationship["source_id"]
                    in stale_managers
                    and relationship["target_id"]
                    in stale_bch
                )
            ]

            unexpected_fk = _unexpected_fk_references(
                cursor,
                stale_assets,
            )

            cursor.execute(
                """
                SELECT COUNT(*) AS count
                FROM nexus.assets
                """
            )
            before_assets = int(
                cursor.fetchone()["count"]
            )

            cursor.execute(
                """
                SELECT COUNT(*) AS count
                FROM nexus.relationships
                """
            )
            before_relationships = int(
                cursor.fetchone()["count"]
            )

            expected_assets = (
                before_assets
                - len(stale_assets)
            )

            expected_relationships = (
                before_relationships
                - len(relationships)
            )

            return {
                "mode": "plan",
                "writeOperations": False,
                "canonical": {
                    "managerAssetId": manager_asset_id,
                    "bchAssetId": bch_asset_id,
                },
                "stale": {
                    "managerAssetIds": stale_managers,
                    "bchAssetIds": stale_bch,
                    "assetCount": len(stale_assets),
                },
                "references": {
                    "auditEvents": audit_events,
                    "currentMetrics": metrics,
                    "blockchainNodes": node_rows,
                    "relationships": len(
                        relationships
                    ),
                },
                "historicalEvidence": {
                    "registrationRowsPreserved": True,
                    "registrationRawPayloadPreserved": True,
                    "registrationResultPreserved": True,
                    "auditMetadataPreserved": True,
                    "contextSnapshotsPreserved": True,
                },
                "guards": {
                    "unexpectedForeignKeys": (
                        unexpected_fk
                    ),
                    "unexpectedRelationships": (
                        unexpected_relationships
                    ),
                    "safeToExecute": not (
                        unexpected_fk
                        or unexpected_relationships
                    ),
                },
                "counts": {
                    "beforeAssets": before_assets,
                    "beforeRelationships": (
                        before_relationships
                    ),
                    "expectedAssets": expected_assets,
                    "expectedRelationships": (
                        expected_relationships
                    ),
                },
                "confirmationRequired": CONFIRMATION,
            }


def _merge_current_metrics(
    cursor,
    *,
    stale_bch: list[str],
    canonical_bch: str,
) -> int:
    if not stale_bch:
        return 0

    cursor.execute(
        """
        INSERT INTO nexus.current_metrics (
            subject_type,
            subject_id,
            metric_name,
            metric_value,
            metric_unit,
            status,
            observed_at,
            dimensions,
            data
        )
        SELECT
            winner.subject_type,
            %s,
            winner.metric_name,
            winner.metric_value,
            winner.metric_unit,
            winner.status,
            winner.observed_at,
            winner.dimensions,
            winner.data
        FROM (
            SELECT DISTINCT ON (
                subject_type,
                metric_name
            )
                subject_type,
                metric_name,
                metric_value,
                metric_unit,
                status,
                observed_at,
                dimensions,
                data
            FROM nexus.current_metrics
            WHERE subject_id = ANY(%s)
               OR subject_id = %s
            ORDER BY
                subject_type,
                metric_name,
                observed_at DESC
        ) AS winner
        ON CONFLICT (
            subject_type,
            subject_id,
            metric_name
        )
        DO UPDATE SET
            metric_value = EXCLUDED.metric_value,
            metric_unit = EXCLUDED.metric_unit,
            status = EXCLUDED.status,
            observed_at = EXCLUDED.observed_at,
            dimensions = EXCLUDED.dimensions,
            data = EXCLUDED.data
        WHERE
            EXCLUDED.observed_at
            > nexus.current_metrics.observed_at
        """,
        (
            canonical_bch,
            stale_bch,
            canonical_bch,
        ),
    )

    cursor.execute(
        """
        DELETE FROM nexus.current_metrics
        WHERE subject_id = ANY(%s)
        """,
        (stale_bch,),
    )

    return cursor.rowcount


def execute_consolidation(
    *,
    manager_asset_id: str,
    bch_asset_id: str,
    confirmation: str,
) -> dict[str, Any]:
    if confirmation != CONFIRMATION:
        raise RuntimeError(
            "Invalid confirmation token. "
            f"Required: {CONFIRMATION}"
        )

    plan = build_plan(
        manager_asset_id=manager_asset_id,
        bch_asset_id=bch_asset_id,
    )

    if not plan["guards"]["safeToExecute"]:
        raise RuntimeError(
            "Consolidation blocked by unexpected "
            "references. Review plan first."
        )

    stale_managers = plan["stale"][
        "managerAssetIds"
    ]
    stale_bch = plan["stale"]["bchAssetIds"]
    stale_assets = stale_managers + stale_bch

    if not stale_assets:
        return {
            **plan,
            "mode": "execute",
            "executed": True,
            "status": "already-consolidated",
        }

    with get_connection() as connection:
        try:
            with connection.cursor() as cursor:
                _canonical_assets(
                    cursor,
                    manager_asset_id=manager_asset_id,
                    bch_asset_id=bch_asset_id,
                )

                # Historical audit metadata stays untouched.
                # Only the indexed FK is reconciled so the
                # history remains attached to the canonical
                # BCH runtime.
                cursor.execute(
                    """
                    UPDATE nexus.audit_events
                    SET asset_id = %s
                    WHERE asset_id = ANY(%s)
                    """,
                    (
                        bch_asset_id,
                        stale_bch,
                    ),
                )
                audit_events_moved = cursor.rowcount

                stale_metrics_deleted = (
                    _merge_current_metrics(
                        cursor,
                        stale_bch=stale_bch,
                        canonical_bch=bch_asset_id,
                    )
                )

                cursor.execute(
                    """
                    DELETE FROM nexus.relationships
                    WHERE (
                        source_id = ANY(%s)
                        OR target_id = ANY(%s)
                    )
                      AND relationship_type = 'manages'
                      AND source = 'seymour-registration'
                    """,
                    (
                        stale_assets,
                        stale_assets,
                    ),
                )
                relationships_deleted = (
                    cursor.rowcount
                )

                # Canonical blockchain_nodes projection
                # already exists and is newer. Historical
                # observations remain in audit evidence.
                cursor.execute(
                    """
                    DELETE FROM nexus.blockchain_nodes
                    WHERE asset_id = ANY(%s)
                    """,
                    (stale_bch,),
                )
                node_rows_deleted = cursor.rowcount

                cursor.execute(
                    """
                    DELETE FROM nexus.assets
                    WHERE asset_id = ANY(%s)
                    """,
                    (stale_assets,),
                )
                assets_deleted = cursor.rowcount

                # --------------------------------------------------
                # Transactional postconditions.
                # --------------------------------------------------

                cursor.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM nexus.assets
                    WHERE asset_id = ANY(%s)
                    """,
                    (stale_assets,),
                )

                if int(cursor.fetchone()["count"]):
                    raise RuntimeError(
                        "Stale assets remain after cleanup."
                    )

                cursor.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM nexus.current_metrics
                    WHERE subject_id = ANY(%s)
                    """,
                    (stale_bch,),
                )

                if int(cursor.fetchone()["count"]):
                    raise RuntimeError(
                        "Stale current metrics remain."
                    )

                cursor.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM nexus.relationships
                    WHERE source_id = ANY(%s)
                       OR target_id = ANY(%s)
                    """,
                    (
                        stale_assets,
                        stale_assets,
                    ),
                )

                if int(cursor.fetchone()["count"]):
                    raise RuntimeError(
                        "Stale relationships remain."
                    )

                cursor.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM nexus.blockchain_nodes
                    WHERE asset_id = ANY(%s)
                    """,
                    (stale_bch,),
                )

                if int(cursor.fetchone()["count"]):
                    raise RuntimeError(
                        "Stale blockchain node rows remain."
                    )

                cursor.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM nexus.audit_events
                    WHERE asset_id = ANY(%s)
                    """,
                    (stale_bch,),
                )

                if int(cursor.fetchone()["count"]):
                    raise RuntimeError(
                        "Stale indexed audit references remain."
                    )

                cursor.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM nexus.blockchain_nodes
                    WHERE asset_id = %s
                      AND coin = 'BCH'
                      AND network = 'mainnet'
                    """,
                    (bch_asset_id,),
                )

                if int(cursor.fetchone()["count"]) != 1:
                    raise RuntimeError(
                        "Canonical BCH node projection "
                        "is missing or ambiguous."
                    )

                cursor.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM nexus.relationships
                    WHERE source_id = %s
                      AND relationship_type = 'manages'
                      AND target_id = %s
                      AND source = 'seymour-registration'
                    """,
                    (
                        manager_asset_id,
                        bch_asset_id,
                    ),
                )

                if int(cursor.fetchone()["count"]) != 1:
                    raise RuntimeError(
                        "Canonical Manager/BCH "
                        "relationship is missing."
                    )

                cursor.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM nexus.assets
                    """
                )
                after_assets = int(
                    cursor.fetchone()["count"]
                )

                cursor.execute(
                    """
                    SELECT COUNT(*) AS count
                    FROM nexus.relationships
                    """
                )
                after_relationships = int(
                    cursor.fetchone()["count"]
                )

                if (
                    after_assets
                    != plan["counts"][
                        "expectedAssets"
                    ]
                ):
                    raise RuntimeError(
                        "Unexpected asset count after "
                        "consolidation."
                    )

                if (
                    after_relationships
                    != plan["counts"][
                        "expectedRelationships"
                    ]
                ):
                    raise RuntimeError(
                        "Unexpected relationship count "
                        "after consolidation."
                    )

            connection.commit()

        except Exception:
            connection.rollback()
            raise

    return {
        "mode": "execute",
        "executed": True,
        "status": "consolidated",
        "canonical": plan["canonical"],
        "removed": {
            "assets": assets_deleted,
            "blockchainNodes": node_rows_deleted,
            "relationships": relationships_deleted,
            "staleCurrentMetrics": (
                stale_metrics_deleted
            ),
        },
        "reconciled": {
            "auditEvents": audit_events_moved,
        },
        "historicalEvidence": (
            plan["historicalEvidence"]
        ),
        "counts": {
            "beforeAssets": (
                plan["counts"]["beforeAssets"]
            ),
            "afterAssets": after_assets,
            "beforeRelationships": (
                plan["counts"][
                    "beforeRelationships"
                ]
            ),
            "afterRelationships": (
                after_relationships
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Consolidate historical Seymour Blockchain "
            "Manager/BCH CMDB identities."
        )
    )

    parser.add_argument(
        "--manager",
        required=True,
        help="Canonical Blockchain Manager asset ID",
    )

    parser.add_argument(
        "--bch",
        required=True,
        help="Canonical BCH blockchain-node asset ID",
    )

    parser.add_argument(
        "--execute",
        action="store_true",
        help="Perform the transactional consolidation",
    )

    parser.add_argument(
        "--confirm",
        default="",
        help="Required execution confirmation token",
    )

    args = parser.parse_args()

    if args.execute:
        result = execute_consolidation(
            manager_asset_id=args.manager,
            bch_asset_id=args.bch,
            confirmation=args.confirm,
        )
    else:
        result = build_plan(
            manager_asset_id=args.manager,
            bch_asset_id=args.bch,
        )

    print(
        json.dumps(
            result,
            indent=2,
            default=str,
        )
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
