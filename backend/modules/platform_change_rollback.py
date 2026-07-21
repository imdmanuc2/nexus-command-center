from backend.services import change_rollback_service as service
def status(_query=None): return {'status':'ok',**service.status()}
def history(query=None):
    query=query or {}; limit=int((query.get('limit') or ['100'])[0]); rows=service.history(limit)
    return {'status':'ok','count':len(rows),'rollbacks':rows}
def create(payload): return {'status':'ok','rollback':service.create(payload)}
def approve(payload): return {'status':'ok','rollback':service.approve(payload)}
def queue(payload): return {'status':'ok','rollback':service.queue(payload)}
