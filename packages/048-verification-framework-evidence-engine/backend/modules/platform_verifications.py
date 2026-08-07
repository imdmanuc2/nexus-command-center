from __future__ import annotations

from backend.db.repositories import verification_repository as repo


def profiles(_query=None):
    return {"status": "ok", "profiles": repo.profiles()}


def create_profile(payload):
    return {"status": "ok", "profile": repo.create_profile(payload or {})}


def runs(query=None):
    query = query or {}
    try:
        limit = int((query.get("limit") or ["100"])[0])
    except (TypeError, ValueError):
        limit = 100
    rows = repo.runs(limit)
    return {"status": "ok", "count": len(rows), "runs": rows}


def run_detail(run_id):
    value = repo.get(run_id)
    if value is None:
        raise LookupError("Verification run not found")
    return {"status": "ok", "run": value}


def queue(payload):
    value = repo.queue(payload or {})
    return {"status": "ok", "run_id": str(value["run_id"]), "run": value}


def retry(run_id):
    current = repo.get(run_id)
    if current is None:
        raise LookupError("Verification run not found")
    value = repo.queue(
        {
            "profileKey": current["profile_key"],
            "changeId": current.get("change_id"),
            "rollbackId": current.get("rollback_id"),
            "targetType": current["target_type"],
            "targetId": current["target_id"],
            "assetId": current.get("asset_id"),
            "transport": current["transport"],
            "parameters": current.get("parameters") or {},
            "context": {
                "retryOf": str(run_id),
                **(current.get("context") or {}),
            },
            "requestedBy": "verification-retry",
        }
    )
    return {"status": "ok", "run_id": str(value["run_id"]), "run": value}
