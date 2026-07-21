from backend.services import service_maintenance_service

def windows(query=None): return service_maintenance_service.windows(query)
def active(query=None): return service_maintenance_service.active(query)
def upcoming(query=None): return service_maintenance_service.upcoming(query)
def history(query=None): return service_maintenance_service.history(query)
def impact_preview(query=None): return service_maintenance_service.impact_preview(query)
def create(data): return service_maintenance_service.create(data)
def start(data): return service_maintenance_service.start(data)
def complete(data): return service_maintenance_service.complete(data)
def cancel(data): return service_maintenance_service.cancel(data)
