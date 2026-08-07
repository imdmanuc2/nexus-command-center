from backend.services import service_impact_service

def dependencies(query=None): return service_impact_service.dependencies(query)
def impact(query=None): return service_impact_service.impact(query)
def root_cause(query=None): return service_impact_service.root_cause(query)
