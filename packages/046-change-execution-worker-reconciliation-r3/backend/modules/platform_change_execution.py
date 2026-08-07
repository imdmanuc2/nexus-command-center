from __future__ import annotations

from backend.db.repositories import change_execution_repository as repo


def _json(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value


def _normalize(obj):
    if isinstance(obj, dict):
        return {k: _normalize(v) for k,v in obj.items()}
    if isinstance(obj, list):
        return [_normalize(v) for v in obj]
    return _json(obj)


def status(query=None):
    data = repo.status()
    return {"status":"ok","source":"nexus-change-execution-worker",**_normalize(data)}


def history(query=None):
    limit = int(((query or {}).get("limit") or ["100"])[0])
    rows = repo.history(limit)
    return {"status":"ok","count":len(rows),"attempts":_normalize(rows)}
