from __future__ import annotations
from backend.db.repositories.policy_repository import list_decisions, list_policies, record_decision, sync_default_policies
from backend.policy.engine import evaluate_operation

def evaluate_payload(payload: dict) -> dict:
    operation=str(payload.get("operation") or payload.get("capability") or "")
    confirmed=bool(payload.get("confirmed", False))
    requested_by=str(payload.get("requestedBy") or "nexus-user")
    target=dict(payload.get("target") or {})
    decision=evaluate_operation(operation, confirmed=confirmed)
    decision_id=record_decision(
        operation=operation, decision=decision.decision, policy_id=decision.policy_id,
        requested_by=requested_by, target_asset_id=str(target.get("assetId") or "") or None,
        playbook_id=str(payload.get("playbookId") or "") or None, confirmed=confirmed,
        reason=decision.reason, context={"target": target},
    )
    return {"status":"ok","decisionId":decision_id,**decision.to_dict()}

def policies_payload() -> dict:
    sync_default_policies(); items=list_policies()
    return {"status":"ok","count":len(items),"policies":items}

def decisions_payload(limit: int = 100) -> dict:
    items=list_decisions(limit)
    return {"status":"ok","count":len(items),"decisions":items}
