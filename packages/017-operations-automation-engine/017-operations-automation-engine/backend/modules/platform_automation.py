from backend.db.repositories.automation_repository import automation_summary,list_actions,list_runs

def actions():
 r=list_actions();return {'status':'ok','source':'nexus-postgresql-platform-automation','count':len(r),'actions':r}
def runs():
 r=list_runs(100);return {'status':'ok','source':'nexus-postgresql-platform-automation','count':len(r),'runs':r}
def summary():
 return {'status':'ok','source':'nexus-postgresql-platform-automation',**automation_summary()}
