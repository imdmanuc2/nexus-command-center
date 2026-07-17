from backend.db.repositories.timeline_repository import list_entries, summary

def timeline():
    data = list_entries(100)
    return {"status":"ok","source":"nexus-postgresql-operations-timeline",
            "count":len(data),"entries":data}

def latest():
    data = list_entries(25)
    return {"status":"ok","source":"nexus-postgresql-operations-timeline",
            "count":len(data),"entries":data}

def timeline_summary():
    return {"status":"ok","source":"nexus-postgresql-operations-timeline",
            **summary(24)}
