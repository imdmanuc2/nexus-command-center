from backend.db.repositories.cmdb_lifecycle_repository import get, update, history

def asset_payload(q):
 a=(q.get('assetId') or [''])[0]
 if not a: raise ValueError('assetId is required')
 return {'status':'ok','asset':get(a)}
def history_payload(q):
 a=(q.get('assetId') or [''])[0]
 if not a: raise ValueError('assetId is required')
 h=history(a,(q.get('limit') or ['100'])[0]); return {'status':'ok','count':len(h),'history':h}
def update_payload(data):
 a=str(data.get('assetId') or '').strip()
 if not a: raise ValueError('assetId is required')
 return {'status':'ok','asset':update(a,data)}
