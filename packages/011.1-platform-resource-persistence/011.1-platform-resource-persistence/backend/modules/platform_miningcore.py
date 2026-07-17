from backend.db.repositories.miningcore_repository import list_miningcore_instances
def instance_list():
    rows=list_miningcore_instances();return {'status':'ok','source':'nexus-postgresql-platform','count':len(rows),'connectedCount':sum(1 for r in rows if r.get('connected')),'instances':rows}
