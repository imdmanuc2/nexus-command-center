from backend.services import dependency_mapping_service as service
def asset(q): return service.asset(q)
def catalog(q=None): return service.catalog(q)
def dependency_map(q): return service.dependency_map(q)
def upsert(data): return service.upsert(data)
