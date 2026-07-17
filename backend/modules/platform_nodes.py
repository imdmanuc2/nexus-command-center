from backend.db.repositories.blockchain_repository import list_blockchain_nodes
def node_list():
    rows=list_blockchain_nodes();return {'status':'ok','source':'nexus-postgresql-platform','count':len(rows),'nodes':rows}
