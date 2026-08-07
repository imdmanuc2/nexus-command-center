from __future__ import annotations
from typing import Any
from backend.db.connection import transaction
from backend.db.repositories import seymour_telemetry_repository

def backfill_latest() -> dict[str, Any]:
    with transaction() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT registration_id,raw_payload "
                "FROM nexus.seymour_registrations "
                "ORDER BY received_at DESC LIMIT 1"
            )
            row = cursor.fetchone()
            if not row:
                return {"status":"no-registration","registrationId":None,"metricsWritten":0}
            payload = row["raw_payload"]
            document = payload.get("document") if isinstance(payload, dict) else None
            if not isinstance(document, dict):
                return {
                    "status":"invalid-document",
                    "registrationId":row["registration_id"],
                    "metricsWritten":0,
                }
            written = seymour_telemetry_repository.project_document(cursor, document)
            return {
                "status":"projected",
                "registrationId":row["registration_id"],
                "metricsWritten":written,
            }

def status() -> dict[str, Any]:
    with transaction() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT subject_id,COUNT(*) AS metric_count,MAX(observed_at) AS last_observed_at "
                "FROM nexus.current_metrics "
                "WHERE subject_type='blockchain-node' "
                "AND data->>'source'='seymour-blockchain-manager' "
                "GROUP BY subject_id ORDER BY last_observed_at DESC"
            )
            rows = [dict(row) for row in cursor.fetchall()]
    return {"status":"ok","source":"seymour-blockchain-manager","subjects":rows}
