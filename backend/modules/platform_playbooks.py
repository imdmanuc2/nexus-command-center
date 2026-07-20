from backend.playbooks.catalog import get_playbook_catalog
from backend.db.repositories.playbook_repository import get_run, list_runs
from backend.services.playbook_engine_service import catalog_payload, execute_playbook

def catalog(query=None): return catalog_payload()
def detail(query):
    playbook_id=(query.get('playbookId') or [''])[0]
    return {"status":"ok","playbook":get_playbook_catalog().get(playbook_id).to_dict()}
def validate(data):
    pid=str(data.get('playbookId') or '')
    return {"status":"ok",**get_playbook_catalog().validate(pid)}
def run(data): return execute_playbook(data)
def runs(query):
    limit=int((query.get('limit') or ['100'])[0]); items=list_runs(limit)
    return {"status":"ok","count":len(items),"runs":items}
def run_detail(query):
    run_id=(query.get('runId') or [''])[0]; item=get_run(run_id)
    if item is None: raise ValueError('Unknown playbook run')
    return {"status":"ok","run":item}
