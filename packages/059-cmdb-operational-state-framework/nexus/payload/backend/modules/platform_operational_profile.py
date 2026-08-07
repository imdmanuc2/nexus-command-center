from backend.services.operational_profile_service import asset as asset_payload, update as update_payload

def asset(query):
    return asset_payload(query)

def update(data):
    return update_payload(data)
