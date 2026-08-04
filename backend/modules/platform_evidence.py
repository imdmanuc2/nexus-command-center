from backend.services import operation_evidence_service as service

def evidence(query=None): return service.list_evidence(query)
def evidence_detail(evidence_id): return service.get_evidence(evidence_id)
def asset_operations(asset_id, query=None): return service.asset_operations(asset_id, query)
def timeline(query=None): return service.timeline(query)
def recommendation_context(query=None): return service.recommendation_context(query)
def status(query=None): return service.status(query)
