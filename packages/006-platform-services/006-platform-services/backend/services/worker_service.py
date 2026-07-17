from backend.db.repositories.worker_repository import list_workers

def workers():
    records=list_workers(); by_type={}; by_status={}; matched=0
    for w in records:
        t=w.get('workerType') or 'unknown'; s=w.get('status') or 'unknown'
        by_type[t]=by_type.get(t,0)+1; by_status[s]=by_status.get(s,0)+1
        matched += 1 if w.get('assetMatched') is True else 0
    return {'status':'ok','source':'nexus-postgresql-platform','count':len(records),'matchedCount':matched,'unmatchedCount':len(records)-matched,'byType':by_type,'byStatus':by_status,'workers':records}
