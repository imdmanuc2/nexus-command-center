from __future__ import annotations

from typing import Any

from backend.db.repositories import service_maintenance_repository as repo
from backend.services import service_impact_service


def _one(query: dict[str, list[str]], key: str, default: str = "") -> str:
    return str((query.get(key) or [default])[0] or default)


def windows(query=None):
    query = query or {}
    status = _one(query, "status") or None
    limit = int(_one(query, "limit", "200"))
    rows = repo.list_windows(status=status, limit=limit)
    return {"status":"ok","source":"nexus-service-maintenance","count":len(rows),"windows":rows}


def active(query=None):
    return windows({"status":["active"], "limit": (query or {}).get("limit", ["200"])})


def upcoming(query=None):
    return windows({"status":["scheduled"], "limit": (query or {}).get("limit", ["200"])})


def history(query=None):
    query = query or {}
    window_id = _one(query, "windowId") or None
    rows = repo.history(window_id, int(_one(query, "limit", "200")))
    return {"status":"ok","count":len(rows),"history":rows}


def create(data: dict[str, Any]):
    targets = data.get("targets") or []
    service_id = str(data.get("serviceId") or "").strip()
    if service_id and not any(t.get("type") == "service" for t in targets):
        targets.append({"type":"service","value":service_id})
    data = {**data, "targets": targets}
    window = repo.create(data)
    return {"status":"ok","window":window,"impactPreview":preview_for_window(window)}


def start(data: dict[str, Any]):
    window_id = str(data.get("windowId") or "")
    if not window_id:
        raise ValueError("windowId is required")
    window = repo.transition(window_id, "started", str(data.get("actor") or "nexus"), str(data.get("message") or ""))
    return {"status":"ok","window":window}


def complete(data: dict[str, Any]):
    window_id = str(data.get("windowId") or "")
    if not window_id:
        raise ValueError("windowId is required")
    window = repo.transition(window_id, "completed", str(data.get("actor") or "nexus"), str(data.get("message") or ""))
    return {"status":"ok","window":window}


def cancel(data: dict[str, Any]):
    window_id = str(data.get("windowId") or "")
    if not window_id:
        raise ValueError("windowId is required")
    window = repo.cancel(window_id, str(data.get("actor") or data.get("cancelledBy") or "nexus"), str(data.get("reason") or ""))
    return {"status":"ok","window":window}


def impact_preview(query=None):
    query = query or {}
    service_id = _one(query, "serviceId")
    asset_id = _one(query, "assetId")
    if not service_id and not asset_id:
        raise ValueError("serviceId or assetId is required")
    if service_id:
        return preview_service(service_id)
    impact = service_impact_service.analyze()
    affected = []
    for svc in impact.get("services", []):
        ids = {a.get("asset_id") for a in svc.get("dependencyAssets", [])}
        if asset_id in ids:
            affected.append({
                "serviceId": svc["serviceId"],
                "serviceName": svc["serviceName"],
                "currentCapacityPercent": svc.get("health", {}).get("capacityPercent", 0),
                "expectedCapacityPercent": max(0, svc.get("health", {}).get("capacityPercent", 0) - 25),
            })
    return {"status":"ok","target":{"type":"asset","value":asset_id},"affectedServices":affected}


def preview_service(service_id: str):
    members = repo.service_members(service_id)
    required = [m for m in members if m.get("required")]
    current_active = [m for m in members if str(m.get("operational_state")).lower() == "active"]
    expected = 0 if required else max(0, len(current_active) - len(members))
    capacity = round((expected / len(members)) * 100, 2) if members else 0
    analysis = service_impact_service.analyze(service_id)
    service = (analysis.get("services") or [{}])[0]
    warnings = []
    if required:
        warnings.append(f"{len(required)} required component(s) will be placed in maintenance.")
    if members:
        warnings.append(f"{len(members)} service member(s) are in scope.")
    return {
        "status":"ok",
        "target":{"type":"service","value":service_id},
        "serviceId":service_id,
        "serviceName":service.get("serviceName", service_id),
        "affectedAssets":members,
        "currentCapacityPercent":service.get("health", {}).get("capacityPercent", 0),
        "expectedCapacityPercent":capacity,
        "warnings":warnings,
    }


def preview_for_window(window: dict[str, Any]):
    previews = []
    for target in window.get("targets", []):
        if target.get("type") == "service":
            previews.append(preview_service(str(target.get("value"))))
    return previews
