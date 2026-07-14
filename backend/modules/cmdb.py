"""CMDB API-facing functions backed by PostgreSQL assets."""
from __future__ import annotations
from typing import Any

from backend.core.cmdb_audit import read_events, summary as legacy_audit_summary
from backend.services import cmdb_service

def assets() -> dict[str, Any]:
    return cmdb_service.list_assets()

def summary() -> dict[str, Any]:
    payload = cmdb_service.summary()
    payload["audit"] = legacy_audit_summary()
    return payload

def audit_events(
    *, asset_id: str | None = None, action: str | None = None,
    source: str | None = None, correlation_id: str | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    events = read_events(
        asset_id=asset_id,
        action=action,
        source=source,
        correlation_id=correlation_id,
        limit=limit,
    )
    return {
        "status": "ok",
        "source": "nexus-postgresql-audit",
        "count": len(events),
        "events": events,
    }
