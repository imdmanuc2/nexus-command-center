from __future__ import annotations
from typing import Any
from backend.capabilities.registry import get_capability_registry
from backend.db.repositories import change_rollback_repository as repo
from backend.transports.registry import get_transport_registry
from backend.transports.target_resolver import resolve_target

def execute_plan(plan: dict[str,Any], worker_id: str):
    aid=repo.start_attempt(plan,worker_id); result={}
    try:
        params=dict(plan.get('parameters') or {}); transport_name=params.pop('transport','ssh')
        registry=get_capability_registry(); cap=registry.resolve(plan['rollback_action']); registry.validate_parameters(cap,params)
        entity=plan.get('asset_id') or plan['target_id']
        target=resolve_target({'entityId':entity,'inputPayload':{'assetId':entity,'transport':transport_name,**params}})
        transport=get_transport_registry().resolve(target.transport)
        out=transport.execute(target=target,argv=cap.build_argv(params),timeout_seconds=int(cap.timeout_seconds)); result=out.to_dict()
        if not out.ok: raise RuntimeError(f"Rollback execution failed with exit code {out.exit_code}: {out.stderr or 'no error output'}")
        verification={}
        if cap.verify_argv:
            v=transport.execute(target=target,argv=cap.verify_argv(params),timeout_seconds=int(cap.timeout_seconds)); verification=v.to_dict()
            if not v.ok: raise RuntimeError('Rollback post-action verification failed')
        repo.finish_success(aid,plan,result,verification)
        return {'status':'succeeded','rollbackId':str(plan['rollback_id']),'result':result,'verification':verification}
    except Exception as exc:
        repo.finish_failure(aid,plan,str(exc),result)
        return {'status':'manual_intervention','rollbackId':str(plan['rollback_id']),'error':str(exc),'result':result}

def run_once(worker_id):
    recovered=repo.reconcile_stale(); plan=repo.claim_next(worker_id)
    if not plan: return {'status':'idle','recovered':recovered}
    result=execute_plan(plan,worker_id); result['recovered']=recovered; return result

def create(payload):
    missing=[k for k in ('changeId','rollbackAction','targetType','targetId') if not payload.get(k)]
    if missing: raise ValueError('Missing required fields: '+', '.join(missing))
    return repo.create_plan(payload)
def approve(payload):
    plan=repo.approve_plan(payload.get('rollbackId',''),payload.get('approvedBy',''))
    if not plan: raise ValueError('Rollback plan was not found or is not awaiting approval')
    return plan
def queue(payload):
    plan=repo.queue_plan(payload.get('rollbackId',''),payload.get('requestedBy',''))
    if not plan: raise ValueError('Rollback plan is not approved or cannot be queued')
    return plan
def status(): return repo.status()
def history(limit=100): return repo.history(limit)
