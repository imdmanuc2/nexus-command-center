from __future__ import annotations
from typing import Any
from backend.db.repositories.operational_profile_repository import get_profile, update_profile


def asset(query: dict[str, list[str]]) -> dict[str, Any]:
    asset_id = (query.get("assetId") or [""])[0]
    if not asset_id:
        raise ValueError("assetId is required")
    return {"status": "ok", "source": "nexus-cmdb-operational-profile", "profile": get_profile(asset_id)}


def update(data: dict[str, Any]) -> dict[str, Any]:
    asset_id = str(data.get("assetId") or "").strip()
    if not asset_id:
        raise ValueError("assetId is required")
    return {"status": "ok", "source": "nexus-cmdb-operational-profile", "profile": update_profile(asset_id, data)}
