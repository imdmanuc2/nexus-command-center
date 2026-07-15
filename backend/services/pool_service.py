from backend.db.repositories.pool_repository import list_pools
from backend.db.repositories.worker_repository import list_workers

def pools():
    pools=list_pools(); workers=list_workers(); by_pool={}
    for w in workers:
        pid=w.get('poolInstanceId')
        if pid: by_pool.setdefault(pid,[]).append(w)
    result=[]
    for p in pools:
        ws=by_pool.get(p.get('poolId'),[])
        result.append({**p,'workerCount':len(ws),'onlineWorkerCount':sum(1 for w in ws if str(w.get('status') or '').lower()=='online'),'currentHashrate':sum(float(w.get('currentHashrate') or 0) for w in ws),'workers':ws})
    return {'status':'ok','source':'nexus-postgresql-platform','count':len(result),'pools':result}
