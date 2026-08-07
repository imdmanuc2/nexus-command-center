from backend.services import change_management_service

def list_changes(query=None): return change_management_service.list_changes(query)
def get_change(change_id): return change_management_service.get_change(change_id)
def history(query=None): return change_management_service.history(query)
def templates(query=None): return change_management_service.templates(query)
def impact_preview(query=None): return change_management_service.impact_preview(query)
def create(data): return change_management_service.create(data)
def approve(change_id,data): return change_management_service.approve(change_id,data)
def execute(change_id,data): return change_management_service.execute(change_id,data)
def rollback(change_id,data): return change_management_service.rollback(change_id,data)
def complete(change_id,data): return change_management_service.complete(change_id,data)
def fail(change_id,data): return change_management_service.fail(change_id,data)
def cancel(change_id,data): return change_management_service.cancel(change_id,data)
