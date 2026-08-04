from __future__ import annotations

from typing import Any
from uuid import uuid4
from psycopg.types.json import Jsonb

from backend.db.connection import get_connection, transaction

MANAGEMENT_MODELS = {"nexus-managed", "customer-managed", "observed"}
LIFECYCLE_STAGES = {"discovered", "provisioning", "commissioning", "production", "maintenance", "decommissioning", "retired"}
HEALTH_STATES = {"healthy", "warning", "critical", "unknown"}
CONNECTIVITY_STATES = {"connected", "disconnected", "intermittent", "unknown"}


def _row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "assetId": row["asset_id"],
        "mission": row.get("mission") or "",
        "role": row.get("operational_role") or "",
        "managementModel": row.get("management_model") or "nexus-managed",
        "lifecycleStage": row.get("lifecycle_stage") or "production",
        "desiredOperationalState": row.get("desired_operational_mode") or "automatic",
        "observedOperationalState": row.get("observed_operational_mode") or "unknown",
        "health": row.get("health_state") or "unknown",
        "connectivity": row.get("connectivity_state") or "unknown",
        "updatedAt": row.get("updated_at").isoformat() if row.get("updated_at") else None,
    }


def get_profile(asset_id: str) -> dict[str, Any]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT asset_id, mission, operational_role, management_model,
                       lifecycle_stage, desired_operational_mode,
                       observed_operational_mode, health_state,
                       connectivity_state, updated_at
                FROM nexus.assets WHERE asset_id=%s
            """, (asset_id,))
            row = cur.fetchone()
    if not row:
        raise KeyError("Asset not found")
    return _row(row)


def _validate(field: str, value: str, allowed: set[str]) -> str:
    normalized = str(value or "").strip().lower()
    if normalized not in allowed:
        raise ValueError(f"Unsupported {field}: {normalized}")
    return normalized


def update_profile(asset_id: str, data: dict[str, Any]) -> dict[str, Any]:
    before = get_profile(asset_id)
    values = {
        "mission": str(data.get("mission", before["mission"])).strip(),
        "role": str(data.get("role", before["role"])).strip(),
        "management": _validate("managementModel", data.get("managementModel", before["managementModel"]), MANAGEMENT_MODELS),
        "lifecycle": _validate("lifecycleStage", data.get("lifecycleStage", before["lifecycleStage"]), LIFECYCLE_STAGES),
        "desired": str(data.get("desiredOperationalState", before["desiredOperationalState"])).strip().lower() or "automatic",
        "observed": str(data.get("observedOperationalState", before["observedOperationalState"])).strip().lower() or "unknown",
        "health": _validate("health", data.get("health", before["health"]), HEALTH_STATES),
        "connectivity": _validate("connectivity", data.get("connectivity", before["connectivity"]), CONNECTIVITY_STATES),
    }
    actor = str(data.get("changedBy") or "nexus")
    reason = str(data.get("reason") or "")
    correlation = str(data.get("correlationId") or f"corr-{uuid4().hex}")
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE nexus.assets SET
                  mission=%(mission)s,
                  operational_role=%(role)s,
                  management_model=%(management)s,
                  lifecycle_stage=%(lifecycle)s,
                  desired_operational_mode=%(desired)s,
                  observed_operational_mode=%(observed)s,
                  health_state=%(health)s,
                  connectivity_state=%(connectivity)s,
                  updated_at=NOW()
                WHERE asset_id=%(asset_id)s
            """, {**values, "asset_id": asset_id})
            if cur.rowcount != 1:
                raise KeyError("Asset not found")
            after = {"assetId": asset_id, **{
                "mission": values["mission"], "role": values["role"],
                "managementModel": values["management"], "lifecycleStage": values["lifecycle"],
                "desiredOperationalState": values["desired"], "observedOperationalState": values["observed"],
                "health": values["health"], "connectivity": values["connectivity"],
            }}
            cur.execute("""
                INSERT INTO nexus.asset_operational_profile_history
                  (asset_id, previous_profile, new_profile, reason, changed_by, source, correlation_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
            """, (asset_id, Jsonb(before), Jsonb(after), reason, actor,
                  str(data.get("source") or "cmdb-operational-profile"), correlation))
    return get_profile(asset_id)
