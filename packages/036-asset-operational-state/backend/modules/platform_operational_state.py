from backend.services.operational_state_service import (
    asset_payload, bulk_payload, history_payload, list_payload,
    set_payload, summary_payload,
)


def assets(query=None): return list_payload(query)
def asset(query): return asset_payload(query)
def summary(): return summary_payload()
def history(query): return history_payload(query)
def set_state(data): return set_payload(data)
def bulk_set_state(data): return bulk_payload(data)
