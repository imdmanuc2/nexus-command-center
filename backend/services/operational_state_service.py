from __future__ import annotations

from typing import Any
from uuid import uuid4

from backend.db.repositories.audit_repository import append_event
from backend.db.repositories.operational_state_repository import (
    SUPPRESSED_STATES, bulk_set_asset_state, get_asset_state,
    list_asset_states, set_asset_state, state_history, state_summary,
)
from backend.services.maintenance_service import entity_status


def _effective(record: dict[str, Any]) -> dict[str, Any]:
    maintenance = entity_status(record["assetType"], record["assetId"])
    effective_state = "maintenance" if maintenance["inMaintenance"] else record["operationalState"]
    return {
        **record,
        "effectiveOperationalState": effective_state,
        "maintenance": maintenance,
        "alertSuppressed": effective_state in SUPPRESSED_STATES or maintenance["suppressAlerts"],
        "recommendationSuppressed": effective_state in SUPPRESSED_STATES or maintenance["suppressRecommendations"],
    }


def list_payload(query: dict[str, list[str]] | None = None) -> dict[str, Any]:
    query = query or {}
    state = (query.get("state") or [None])[0]
    asset_type = (query.get("assetType") or [None])[0]
    limit = int((query.get("limit") or ["500"])[0])
    assets = [_effective(r) for r in list_asset_states(state, asset_type, limit)]
    return {"status": "ok", "source": "nexus-operational-state", "count": len(assets), "assets": assets}


def asset_payload(query: dict[str, list[str]]) -> dict[str, Any]:
    asset_id = (query.get("assetId") or [""])[0]
    if not asset_id:
        raise ValueError("assetId is required")
    return {"status": "ok", "asset": _effective(get_asset_state(asset_id))}


def summary_payload() -> dict[str, Any]:
    return {"status": "ok", "source": "nexus-operational-state", **state_summary()}


def history_payload(query: dict[str, list[str]]) -> dict[str, Any]:
    asset_id = (query.get("assetId") or [""])[0]
    if not asset_id:
        raise ValueError("assetId is required")
    records = state_history(asset_id, int((query.get("limit") or ["100"])[0]))
    return {"status": "ok", "count": len(records), "history": records}


def set_payload(data: dict[str, Any]) -> dict[str, Any]:
    asset_id = str(data.get("assetId") or "").strip()
    if not asset_id:
        raise ValueError("assetId is required")
    actor = str(data.get("changedBy") or "nexus")
    correlation = str(data.get("correlationId") or f"corr-{uuid4().hex}")
    before = get_asset_state(asset_id)
    asset = set_asset_state(asset_id, data.get("state"), reason=str(data.get("reason") or ""),
                            changed_by=actor, source=str(data.get("source") or "operational-state"),
                            correlation_id=correlation, metadata=data.get("metadata") or {})
    append_event({
        "category": "operations", "action": "asset.operational-state.changed",
        "assetId": asset_id, "assetType": asset["assetType"], "assetName": asset["assetName"],
        "source": "operational-state", "reason": str(data.get("reason") or ""),
        "correlationId": correlation, "actor": {"type": "user", "id": actor},
        "changes": [{"field": "operationalState", "before": before["operationalState"], "after": asset["operationalState"]}],
    })
    return {"status": "ok", "asset": _effective(asset)}


def bulk_payload(data: dict[str, Any]) -> dict[str, Any]:
    ids = data.get("assetIds") or []
    actor = str(data.get("changedBy") or "nexus")
    correlation = str(data.get("correlationId") or f"corr-{uuid4().hex}")
    records = bulk_set_asset_state(ids, data.get("state"), reason=str(data.get("reason") or ""),
                                   changed_by=actor, source=str(data.get("source") or "operational-state-bulk"),
                                   correlation_id=correlation, metadata=data.get("metadata") or {})
    for asset in records:
        append_event({"category":"operations", "action":"asset.operational-state.changed",
            "assetId":asset["assetId"], "assetType":asset["assetType"], "assetName":asset["assetName"],
            "source":"operational-state-bulk", "reason":str(data.get("reason") or ""),
            "correlationId":correlation, "actor":{"type":"user","id":actor},
            "metadata":{"bulk":True,"state":asset["operationalState"]}})
    return {"status":"ok", "updatedCount":len(records), "assets":[_effective(r) for r in records]}


def should_suppress_alert(asset_id: str) -> bool:
    return _effective(get_asset_state(asset_id))["alertSuppressed"]
