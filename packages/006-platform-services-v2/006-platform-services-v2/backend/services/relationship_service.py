from backend.db.repositories.relationship_repository import list_relationships

def relationships():
    records=list_relationships(); by_type={}
    for r in records:
        t=r.get('relationshipType') or 'unknown'; by_type[t]=by_type.get(t,0)+1
    return {'status':'ok','source':'nexus-postgresql-platform','count':len(records),'byType':by_type,'relationships':records}
