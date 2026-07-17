from __future__ import annotations
import contextlib,io
from backend.db.repositories.automation_repository import create_run,get_action,list_queued_runs,mark_run_running,complete_run
from backend.jobs.platform_resource_sync import synchronize_platform_resources

def request_automation(*,action_id,entity_type,entity_id,recommendation_id=None,requested_by='operator',dry_run=True,input_payload=None):
 action=get_action(action_id)
 if action is None: raise ValueError(f'Unknown or disabled action: {action_id}')
 if action['entityType'] not in {'*',entity_type}: raise ValueError(f'Action {action_id} does not support {entity_type}')
 if dry_run and not action['supportsDryRun']: raise ValueError(f'Action {action_id} does not support dry-run')
 return create_run(action_id=action_id,recommendation_id=recommendation_id,entity_type=entity_type,entity_id=entity_id,requested_by=requested_by,dry_run=dry_run,input_payload=input_payload or {},execution_plan={'action':action,'entityType':entity_type,'entityId':entity_id,'dryRun':dry_run},requires_approval=action['requiresApproval'])

def _execute(run):
 if run['dryRun']: return {'dryRun':True,'wouldExecute':run['actionId'],'entityType':run['entityType'],'entityId':run['entityId']}
 if run['actionId']=='refresh-platform-sync':
  from backend.jobs.platform_sync_job import run_once
  buf=io.StringIO()
  with contextlib.redirect_stdout(buf): return run_once(stale_seconds=300,dry_run=False)
 if run['actionId']=='refresh-resource-sync': return synchronize_platform_resources(stale_seconds=300)
 return {'status':'planned','message':'Executor integration is pending; no remote command was executed.'}

def process_queued_automations(limit=25):
 queued=list_queued_runs(limit);completed=failed=0;results=[]
 for run in queued:
  if not mark_run_running(run['runId']): continue
  try:
   result=_execute(run);complete_run(run_id=run['runId'],status='completed',result_payload=result);completed+=1;results.append({'runId':run['runId'],'status':'completed','result':result})
  except Exception as exc:
   complete_run(run_id=run['runId'],status='failed',result_payload={},error_message=str(exc));failed+=1;results.append({'runId':run['runId'],'status':'failed','error':str(exc)})
 return {'status':'ok','source':'nexus-operations-automation-engine','queuedRuns':len(queued),'completedRuns':completed,'failedRuns':failed,'results':results}
