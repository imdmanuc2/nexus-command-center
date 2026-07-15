from backend.db.repositories.asset_repository import list_assets
from backend.db.repositories.pool_repository import list_pools
from backend.db.repositories.worker_repository import list_workers
from backend.db.repositories.workload_repository import list_workloads
ONLINE={'online','healthy','running','active','connected'}
def fleet():
    assets=list_assets(); workers=list_workers(); pools=list_pools(); workloads=list_workloads()
    asset_types={}; worker_types={}; workload_types={}
    for a in assets:
        t=a.get('assetType') or 'unknown'; asset_types[t]=asset_types.get(t,0)+1
    for w in workers:
        t=w.get('workerType') or 'unknown'; worker_types[t]=worker_types.get(t,0)+1
    for w in workloads:
        t=w.get('workloadType') or 'unknown'; workload_types[t]=workload_types.get(t,0)+1
    ow=[w for w in workers if str(w.get('status') or '').lower() in ONLINE]
    op=[p for p in pools if str(p.get('status') or '').lower() in ONLINE]
    denom=len(workers)+len(pools); health=round(((len(ow)+len(op))/denom)*100,2) if denom else 100.0
    matched=sum(1 for w in workers if w.get('assetMatched') is True)
    return {'status':'ok','source':'nexus-postgresql-platform','fleetHealth':health,'fleetHashrate':sum(float(w.get('currentHashrate') or 0) for w in ow),'hashrateUnit':'H/s','assets':{'total':len(assets),'byType':asset_types},'workers':{'total':len(workers),'online':len(ow),'offline':len(workers)-len(ow),'matched':matched,'unmatched':len(workers)-matched,'byType':worker_types},'pools':{'total':len(pools),'online':len(op),'offline':len(pools)-len(op)},'workloads':{'total':len(workloads),'byType':workload_types},'compute':{'asicWorkers':worker_types.get('asic',0),'cpuWorkers':worker_types.get('cpu',0),'gpuWorkers':worker_types.get('gpu',0),'fpgaWorkers':worker_types.get('fpga',0),'aiWorkloads':sum(v for k,v in workload_types.items() if str(k).startswith('ai-')),'miningWorkloads':workload_types.get('crypto-mining',0)}}
