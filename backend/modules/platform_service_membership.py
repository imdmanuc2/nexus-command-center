from backend.services import service_membership_service


def reconcile(data=None):
    data = data or {}
    return service_membership_service.reconcile(data.get('triggerSource', 'api'))


def rules(query=None):
    return service_membership_service.rules(query)


def runs(query=None):
    return service_membership_service.runs(query)
