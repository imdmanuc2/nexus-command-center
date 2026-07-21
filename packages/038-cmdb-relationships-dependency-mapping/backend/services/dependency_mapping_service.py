from backend.db.repositories import dependency_repository as repo

def _q(q,k,default=''):
 v=(q.get(k) or [default])[0]; return v
def asset(q):
 aid=_q(q,'assetId');
 if not aid: raise ValueError('assetId is required')
 return {'status':'ok','source':'nexus-cmdb-dependencies','assetId':aid,'capability':repo.capability(aid),'workloads':repo.workloads(aid),'relationships':repo.for_asset(aid)}
def catalog(q=None): return {'status':'ok','relationshipTypes':repo.catalog(),'computeKinds':['asic','gpu','cpu','fpga','hybrid','general'],'workloadCategories':['mining','ai-inference','ai-training','gpu-rental','cpu-rental','rendering','video-encoding','general-compute']}
def dependency_map(q):
 aid=_q(q,'assetId');
 if not aid: raise ValueError('assetId is required')
 return {'status':'ok',**repo.map_asset(aid,int(_q(q,'depth','3')))}
def upsert(data): return {'status':'ok','relationship':repo.upsert(data)}
