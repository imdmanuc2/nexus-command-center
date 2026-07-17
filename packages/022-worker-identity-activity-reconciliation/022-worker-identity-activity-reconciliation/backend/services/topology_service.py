from backend.db.repositories.asset_repository import list_assets
from backend.db.repositories.pool_repository import list_pools
from backend.db.repositories.worker_repository import list_active_workers
from backend.db.repositories.workload_repository import list_workloads
from backend.db.repositories.relationship_repository import list_relationships

def topology():
    assets=list_assets(); pools=list_pools(); workers=list_active_workers(); workloads=list_workloads(); rels=list_relationships(); nodes=[]
    for a in assets: nodes.append({'id':a['id'],'nodeType':'asset','assetType':a.get('assetType'),'label':a.get('friendlyName'),'status':a.get('observedState',{}).get('status') or a.get('lifecycleStatus') or 'unknown','properties':a})
    for p in pools: nodes.append({'id':p['poolId'],'nodeType':'pool','assetType':'pool','label':p.get('name'),'status':p.get('status'),'properties':p})
    for w in workers: nodes.append({'id':w['workerId'],'nodeType':'worker','assetType':w.get('workerType'),'label':w.get('displayName'),'status':w.get('status'),'properties':w})
    for w in workloads: nodes.append({'id':w['workloadId'],'nodeType':'workload','assetType':w.get('workloadType'),'label':w.get('name'),'status':w.get('status'),'properties':w})
    edges=[{'id':r['relationshipId'],'source':r['sourceId'],'target':r['targetId'],'type':r['relationshipType'],'status':r.get('status'),'confidence':r.get('confidence'),'properties':r.get('metadata') or {}} for r in rels]
    return {'status':'ok','source':'nexus-postgresql-platform','counts':{'nodes':len(nodes),'edges':len(edges),'assets':len(assets),'workers':len(workers),'pools':len(pools),'workloads':len(workloads)},'nodes':nodes,'edges':edges}
