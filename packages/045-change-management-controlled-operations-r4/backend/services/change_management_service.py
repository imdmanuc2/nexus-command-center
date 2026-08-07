from __future__ import annotations

from typing import Any

from backend.db.repositories import change_management_repository as repo
from backend.services import service_impact_service, service_maintenance_service


def _one(query, key, default=""):
    return str(((query or {}).get(key) or [default])[0] or default)


def _json(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _normalize(obj):
    if isinstance(obj, dict):
        return {camel(k): _normalize(v) for k,v in obj.items()}
    if isinstance(obj, list):
        return [_normalize(v) for v in obj]
    return _json(obj)


def camel(name):
    parts = str(name).split("_")
    return parts[0] + "".join(p[:1].upper()+p[1:] for p in parts[1:])


def templates(query=None):
    rows = repo.list_templates(_one(query,"all","false").lower() != "true")
    return {"status":"ok","count":len(rows),"templates":_normalize(rows)}


def list_changes(query=None):
    rows = repo.list_changes(_one(query,"status") or None, int(_one(query,"limit","200")))
    return {"status":"ok","source":"nexus-change-management","count":len(rows),"changes":_normalize(rows)}


def get_change(change_id):
    return {"status":"ok","change":_normalize(repo.get_change(change_id))}


def history(query=None):
    rows = repo.history(_one(query,"changeId") or None, int(_one(query,"limit","300")))
    return {"status":"ok","count":len(rows),"history":_normalize(rows)}


def impact_preview(query=None):
    target_id = _one(query,"targetId")
    target_type = _one(query,"targetType","asset")
    service_id = _one(query,"serviceId")
    if not target_id and not service_id:
        raise ValueError("targetId or serviceId is required")
    if service_id:
        impact = service_maintenance_service.preview_service(service_id)
    elif target_type == "asset":
        impact = service_maintenance_service.impact_preview({"assetId":[target_id]})
    else:
        impact = {"status":"ok","target":{"type":target_type,"value":target_id},"affectedServices":[]}
    return {"status":"ok","impact":impact}


def _impact_for(data):
    service_id = str(data.get("serviceId") or "")
    target_id = str(data.get("targetId") or "")
    target_type = str(data.get("targetType") or "asset")
    if service_id:
        return service_maintenance_service.preview_service(service_id)
    if target_id and target_type == "asset":
        return service_maintenance_service.impact_preview({"assetId":[target_id]})
    return {"status":"ok","target":{"type":target_type,"value":target_id},"affectedServices":[]}


def _maintenance_for(data):
    window_id = str(data.get("maintenanceWindowId") or "")
    if not window_id:
        return {"required":bool(data.get("maintenanceRequired",False)),"window":None}
    from backend.db.repositories.maintenance_repository import get_window
    return {"required":bool(data.get("maintenanceRequired",False)),"window":get_window(window_id)}


def create(data: dict[str, Any]):
    impact = _impact_for(data)
    maintenance = _maintenance_for(data)
    change = repo.create_change(data, impact, maintenance)
    return {"status":"ok","change":_normalize(change)}


def approve(change_id, data):
    actor = str(data.get("actor") or data.get("approvedBy") or "operator")
    return {"status":"ok","change":_normalize(repo.approve(change_id,actor,str(data.get("reason") or "")))}


def execute(change_id, data):
    actor = str(data.get("actor") or "operator")
    change = repo.get_change(change_id)
    if change.get("maintenance_required") and not change.get("maintenance_window_id"):
        raise ValueError("An approved maintenance window is required before execution")
    return {"status":"ok","change":_normalize(repo.queue_execution(change_id,actor))}


def rollback(change_id, data):
    actor = str(data.get("actor") or "operator")
    return {"status":"ok","change":_normalize(repo.create_rollback(change_id,actor))}


def complete(change_id, data):
    return {"status":"ok","change":_normalize(repo.terminal(
        change_id,"completed",str(data.get("actor") or "operations-engine"),
        str(data.get("message") or "Change completed successfully."),
        data.get("result") or {},
    ))}


def fail(change_id, data):
    return {"status":"ok","change":_normalize(repo.terminal(
        change_id,"failed",str(data.get("actor") or "operations-engine"),
        str(data.get("message") or "Change execution failed."),
        data.get("result") or {},
    ))}


def cancel(change_id, data):
    return {"status":"ok","change":_normalize(repo.terminal(
        change_id,"cancelled",str(data.get("actor") or "operator"),
        str(data.get("reason") or "Change cancelled."),
        {},
    ))}
