from __future__ import annotations
from uuid import uuid4
from backend.capabilities.registry import get_capability_registry
from backend.executors.managed_host_executor import ManagedHostExecutor
from backend.playbooks.catalog import get_playbook_catalog
from backend.playbooks.conditions import evaluate_condition
from backend.playbooks.variables import build_variables, resolve_variables
from backend.db.repositories.playbook_repository import add_step, create_run, finish_run, finish_step, sync_catalog
from backend.services.policy_engine_service import evaluate_payload


def _executor(): return ManagedHostExecutor()
def catalog_payload():
    items=get_playbook_catalog().list(); sync_catalog(items)
    return {"status":"ok","source":"nexus-enterprise-playbook-engine","count":len(items),"playbooks":items}
def execute_playbook(payload):
    playbook=get_playbook_catalog().get(str(payload.get('playbookId') or ''))
    target=dict(payload.get('target') or {})
    target_id=str(target.get('assetId') or target.get('entityId') or '')
    if not target_id: raise ValueError('target.assetId is required')
    variables=build_variables(playbook.variables,dict(payload.get('variables') or {}))
    policy=evaluate_payload({
        'operation': f'playbook:{playbook.playbook_id}',
        'playbookId': playbook.playbook_id,
        'requestedBy': str(payload.get('requestedBy') or 'nexus-user'),
        'target': target,
        'confirmed': bool(payload.get('confirmed', False)),
    })
    if policy['decision'] == 'deny':
        return {'status':'denied','playbookId':playbook.playbook_id,'policy':policy}
    if policy['decision'] == 'confirmation_required':
        return {'status':'confirmation_required','playbookId':playbook.playbook_id,'policy':policy}
    run_id='pbr-'+uuid4().hex
    run={"runId":run_id,"playbookId":playbook.playbook_id,"playbookVersion":playbook.version,
         "targetAssetId":target_id,"targetType":str(target.get('type') or ''),"status":"running",
         "requestedBy":str(payload.get('requestedBy') or 'nexus-user'),"variables":variables}
    create_run(run); context={"previous":{}}
    results=[]
    try:
        for position,step in enumerate(playbook.steps,1):
            if not evaluate_condition(step.when,context):
                results.append({"stepId":step.step_id,"status":"skipped"}); context['previous']=results[-1]; continue
            params=resolve_variables(step.parameters,variables)
            definition=get_capability_registry().resolve(step.capability)
            get_capability_registry().validate_parameters(definition,params)
            step_run_id=add_step(run_id,step,position,params)
            action_run={"runId":f"{run_id}:{step.step_id}","actionId":step.capability,"entityType":run['targetType'] or 'asset',"entityId":target_id,"status":"running","requestedBy":run['requestedBy'],"inputPayload":{"parameters":params}}
            try:
                result=_executor().execute(action_run).to_dict()
                status='success' if result.get('status') not in {'failed','error'} else 'failed'
                finish_step(step_run_id,status,result,result.get('summary') if status=='failed' else None)
            except Exception as exc:
                result={"status":"failed","error":str(exc)}; status='failed'; finish_step(step_run_id,status,result,str(exc))
            row={"stepId":step.step_id,"capability":step.capability,"status":status,"result":result}; results.append(row); context['previous']=row
            if status=='failed' and not step.continue_on_error: raise RuntimeError(f"Step {step.step_id} failed: {result.get('error') or result.get('summary')}")
        summary={"steps":results,"completedSteps":sum(1 for r in results if r['status']=='success')}
        finish_run(run_id,'completed',summary); return {"status":"completed","runId":run_id,"playbookId":playbook.playbook_id,"result":summary}
    except Exception as exc:
        finish_run(run_id,'failed',{"steps":results},str(exc)); return {"status":"failed","runId":run_id,"playbookId":playbook.playbook_id,"error":str(exc),"steps":results}
