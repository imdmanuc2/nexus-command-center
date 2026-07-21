from backend.services import service_topology_service

def topology(query=None):
    return service_topology_service.topology(query)

def detail(query):
    return service_topology_service.detail(query)
