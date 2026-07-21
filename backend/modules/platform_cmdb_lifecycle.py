from backend.services.cmdb_lifecycle_service import asset_payload,history_payload,update_payload
def asset(q): return asset_payload(q)
def history(q): return history_payload(q)
def update(data): return update_payload(data)
