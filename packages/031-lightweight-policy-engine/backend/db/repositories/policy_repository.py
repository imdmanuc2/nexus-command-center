from __future__ import annotations
from psycopg.types.json import Jsonb
from backend.db.connection import get_connection, transaction

DEFAULT_POLICIES = [
    ("v1-allow-read", "Allow read-only operations", "read", "allow", False, 10),
    ("v1-confirm-destructive", "Confirm destructive operations", "destructive", "confirmation_required", True, 20),
    ("v1-allow-configuration", "Allow configuration operations", "configuration", "allow", False, 30),
    ("v1-allow-playbook", "Allow validated playbooks", "playbook", "allow", False, 40),
    ("v1-deny-arbitrary-command", "Deny arbitrary commands", "arbitrary-command", "deny", False, 1),
]

def sync_default_policies() -> int:
    with transaction() as conn:
        with conn.cursor() as cur:
            for row in DEFAULT_POLICIES:
                cur.execute("""INSERT INTO nexus.execution_policies
                    (policy_id,name,operation_class,decision,requires_confirmation,priority,enabled)
                    VALUES(%s,%s,%s,%s,%s,%s,TRUE)
                    ON CONFLICT(policy_id) DO UPDATE SET name=EXCLUDED.name,operation_class=EXCLUDED.operation_class,
                    decision=EXCLUDED.decision,requires_confirmation=EXCLUDED.requires_confirmation,
                    priority=EXCLUDED.priority,enabled=TRUE,updated_at=NOW()""", row)
    return len(DEFAULT_POLICIES)

def record_decision(*, operation: str, decision: str, policy_id: str, requested_by: str,
                    target_asset_id: str | None = None, playbook_id: str | None = None,
                    confirmed: bool = False, reason: str = "", context: dict | None = None) -> str:
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO nexus.policy_decisions
                (operation,decision,policy_id,requested_by,target_asset_id,playbook_id,confirmed,reason,context)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING decision_id""",
                (operation,decision,policy_id,requested_by,target_asset_id,playbook_id,confirmed,reason,Jsonb(context or {})))
            return str(cur.fetchone()["decision_id"])

def list_policies() -> list[dict]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM nexus.execution_policies ORDER BY priority, policy_id")
            return [dict(row) for row in cur.fetchall()]

def list_decisions(limit: int = 100) -> list[dict]:
    limit=max(1,min(int(limit),500))
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM nexus.policy_decisions ORDER BY created_at DESC LIMIT %s", (limit,))
            return [dict(row) for row in cur.fetchall()]
