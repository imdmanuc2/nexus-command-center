from backend.services import service_operations_service


def health():
    return service_operations_service.health()


def dashboard(query=None):
    return service_operations_service.dashboard(query)


def service_health(query=None):
    return service_operations_service.service_health(query)


def incidents(query=None):
    return service_operations_service.incidents(query)


def capacity(query=None):
    return service_operations_service.capacity(query)
