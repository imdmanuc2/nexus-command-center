"""PostgreSQL-backed CMDB application service."""
from __future__ import annotations
from typing import Any
from backend.db.repositories import asset_repository

def list_assets(**filters: Any) -> dict[str, Any]:
    records = asset_repository.list_assets(**filters)
    return {
        "status": "ok",
        "source": "nexus-postgresql-cmdb",
        "count": len(records),
        "assets": records,
    }

def get_asset(asset_id: str) -> dict[str, Any]:
    record = asset_repository.get_asset(asset_id)
    return {
        "status": "ok" if record else "not-found",
        "source": "nexus-postgresql-cmdb",
        "asset": record,
    }

def summary() -> dict[str, Any]:
    return {
        "status": "ok",
        "source": "nexus-postgresql-cmdb",
        **asset_repository.summary(),
    }
