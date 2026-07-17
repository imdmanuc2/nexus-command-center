"""PostgreSQL-backed CMDB audit compatibility layer."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
from backend.db.repositories import audit_repository

DEFAULT_IGNORED_FIELDS = {"updatedAt","lastSeen","last_seen","observedAt","observed_at",
                          "telemetry","hashrate","temperature"}

def now_iso(): return datetime.now(timezone.utc).isoformat()
def _safe(v):
    try: json.dumps(v); return v
    except (TypeError, ValueError): return str(v)
def _changes(before, after):
    before, after = before or {}, after or {}
    return [{"field": k, "before": _safe(before.get(k)), "after": _safe(after.get(k))}
            for k in sorted(set(before)|set(after))
            if k not in DEFAULT_IGNORED_FIELDS and before.get(k) != after.get(k)]

def append_event(*, action, asset_id=None, asset_type=None, asset_name=None,
                 actor_type="system", actor_id="nexus", source="cmdb", reason="",
                 correlation_id=None, confidence=None, before=None, after=None, metadata=None):
    changes = _changes(before, after)
    if action == "asset.updated" and not changes: return None
    event = {"eventId": f"audit-{uuid4().hex}", "timestamp": now_iso(), "category": "cmdb",
             "action": action, "assetId": asset_id or "", "assetType": asset_type or "",
             "assetName": asset_name or "", "actor": {"type": actor_type, "id": actor_id},
             "source": source, "reason": reason,
             "correlationId": correlation_id or f"corr-{uuid4().hex}",
             "confidence": confidence, "changes": changes, "metadata": metadata or {}}
    return audit_repository.append_event(event)

def read_events(**kwargs): return audit_repository.read_events(**kwargs)
def summary(): return audit_repository.summary()
