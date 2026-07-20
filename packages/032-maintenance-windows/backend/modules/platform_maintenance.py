from backend.services.maintenance_service import (
    cancel_payload,
    create_payload,
    entity_status,
    window_payload,
    windows_payload,
)


def windows(query=None): return windows_payload(query)
def window(query): return window_payload(query)
def create(data): return create_payload(data)
def cancel(data): return cancel_payload(data)
def status(query):
    entity_type = (query.get("entityType") or [""])[0]
    entity_id = (query.get("entityId") or [""])[0]
    if not entity_type or not entity_id:
        raise ValueError("entityType and entityId are required")
    return {"status": "ok", **entity_status(entity_type, entity_id)}
