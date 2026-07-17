from backend.db.repositories.workload_repository import list_workloads

def workloads():
    records=list_workloads(); by_type={}; by_status={}
    for w in records:
        t=w.get('workloadType') or 'unknown'; s=w.get('status') or 'unknown'
        by_type[t]=by_type.get(t,0)+1; by_status[s]=by_status.get(s,0)+1
    return {'status':'ok','source':'nexus-postgresql-platform','count':len(records),'byType':by_type,'byStatus':by_status,'workloads':records}
