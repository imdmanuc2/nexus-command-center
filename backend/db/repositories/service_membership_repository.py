from __future__ import annotations

from backend.db.connection import get_connection
from psycopg.types.json import Jsonb


def _rows(sql, args=()):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, args)
            return [dict(row) for row in cur.fetchall()]


def rules():
    return _rows("""
        SELECT * FROM nexus.business_service_membership_rules
        WHERE enabled=TRUE ORDER BY priority, rule_id
    """)


def candidates():
    return _rows("""
        SELECT a.asset_id, a.asset_type, a.canonical_type, a.name, a.friendly_name,
               a.display_name, a.purpose, a.primary_role, a.coin, a.business_service,
               a.lifecycle_status, a.operational_state, a.capabilities, a.metadata,
               COALESCE(array_agg(DISTINCT w.workload_category)
                 FILTER (WHERE w.workload_category IS NOT NULL), ARRAY[]::text[]) AS workload_categories,
               c.compute_kind
        FROM nexus.assets a
        LEFT JOIN nexus.workload_assignments w
          ON w.asset_id=a.asset_id AND w.status IN ('assigned','active','running')
        LEFT JOIN nexus.compute_capabilities c ON c.asset_id=a.asset_id
        WHERE a.retired_at IS NULL
          AND COALESCE(a.lifecycle_status,'managed') NOT IN ('retired','decommissioned','deleted')
        GROUP BY a.asset_id, c.compute_kind
        ORDER BY a.name, a.asset_id
    """)


def start_run(run_id, trigger_source):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO nexus.business_service_reconciliation_runs
                (run_id,status,trigger_source) VALUES (%s,'running',%s)
            """, (run_id, trigger_source))
        conn.commit()


def upsert_membership(match, run_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO nexus.business_service_members
                (membership_id,service_id,asset_id,role,required,weight,source,confidence,
                 active,manually_managed,reconciliation_key,metadata,last_reconciled_at,updated_at)
                VALUES (%s,%s,%s,%s,%s,1,'automatic-reconciliation',%s,
                        TRUE,FALSE,%s,%s,NOW(),NOW())
                ON CONFLICT(service_id,asset_id,role) DO UPDATE SET
                  required=EXCLUDED.required,
                  confidence=EXCLUDED.confidence,
                  active=TRUE,
                  reconciliation_key=EXCLUDED.reconciliation_key,
                  metadata=EXCLUDED.metadata,
                  last_reconciled_at=NOW(),
                  updated_at=NOW()
                RETURNING (xmax = 0) AS inserted
            """, (
                match['membership_id'], match['service_id'], match['asset_id'],
                match['role'], match['required'], match['confidence'],
                run_id, Jsonb(match['metadata']),
            ))
            inserted = bool(cur.fetchone()['inserted'])
        conn.commit()
    return inserted


def retire_unmatched(run_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE nexus.business_service_members
                SET active=FALSE, updated_at=NOW()
                WHERE source='automatic-reconciliation'
                  AND manually_managed=FALSE
                  AND active=TRUE
                  AND reconciliation_key <> %s
                RETURNING membership_id
            """, (run_id,))
            count = len(cur.fetchall())
        conn.commit()
    return count


def finish_run(run_id, status, counters, error=''):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE nexus.business_service_reconciliation_runs SET
                  status=%s, assets_evaluated=%s, memberships_matched=%s,
                  memberships_created=%s, memberships_updated=%s,
                  memberships_retired=%s, summary=%s, error=%s,
                  completed_at=NOW()
                WHERE run_id=%s
            """, (
                status, counters.get('assetsEvaluated',0), counters.get('membershipsMatched',0),
                counters.get('membershipsCreated',0), counters.get('membershipsUpdated',0),
                counters.get('membershipsRetired',0), Jsonb(counters), error, run_id,
            ))
        conn.commit()


def runs(limit=25):
    return _rows("""
        SELECT * FROM nexus.business_service_reconciliation_runs
        ORDER BY started_at DESC LIMIT %s
    """, (max(1, min(int(limit), 100)),))
