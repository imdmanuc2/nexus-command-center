from __future__ import annotations
from typing import Any
from psycopg.types.json import Jsonb
from backend.db.connection import get_connection,transaction

def record_identity_reconciliation(*,entity_type:str,canonical_key:str,canonical_id:str,incoming_id:str,source_system:str,source_identity:str,action:str,details:dict[str,Any]|None=None)->None:
    with transaction() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO nexus.identity_reconciliation_audit(
                    entity_type,canonical_key,canonical_id,incoming_id,
                    source_system,source_identity,action,details)
                VALUES(%s,%s,%s,%s,%s,%s,%s,%s)
            """,(entity_type,canonical_key,canonical_id,incoming_id,source_system,source_identity,action,Jsonb(details or {})))

def identity_summary()->dict[str,Any]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) audit_count,
                COUNT(*) FILTER(WHERE action='reconciled-existing') reconciled_existing,
                COUNT(*) FILTER(WHERE action='inserted-new') inserted_new,
                MAX(occurred_at) latest_at
                FROM nexus.identity_reconciliation_audit
            """)
            row=cursor.fetchone()
    return {'auditCount':row['audit_count'],'reconciledExisting':row['reconciled_existing'],'insertedNew':row['inserted_new'],'latestAt':row['latest_at'].isoformat() if row['latest_at'] else None}
