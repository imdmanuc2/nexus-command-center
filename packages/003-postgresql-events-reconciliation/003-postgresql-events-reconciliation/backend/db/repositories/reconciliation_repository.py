"""PostgreSQL repository for reconciliation review cases."""
from uuid import uuid4
from psycopg.types.json import Jsonb
from backend.db.connection import get_connection

def create_case(observation_id, case_type, candidate_asset_id=None, confidence=None,
                evidence=None, conflicts=None):
    case_id = f"case-{uuid4().hex}"
    with get_connection() as c:
        with c.cursor() as cur:
            cur.execute("""INSERT INTO nexus.reconciliation_cases (
                case_id, observation_id, candidate_asset_id, case_type, status,
                confidence, evidence, conflicts
              ) VALUES (%s,%s,%s,%s,'open',%s,%s,%s) RETURNING *""",
              (case_id, observation_id, candidate_asset_id, case_type, confidence,
               Jsonb(evidence or []), Jsonb(conflicts or [])))
            row = cur.fetchone()
        c.commit()
    return dict(row)

def list_cases(status="open", limit=200):
    with get_connection() as c:
        with c.cursor() as cur:
            cur.execute("""SELECT * FROM nexus.reconciliation_cases
              WHERE status=%s ORDER BY created_at DESC LIMIT %s""",
              (status, max(1, min(int(limit), 5000))))
            return [dict(r) for r in cur.fetchall()]
