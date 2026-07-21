from typing import Any
from backend.db.repositories.deployment_repository import register_package,list_packages,create_job,list_jobs,get_job,set_status
from backend.db.repositories.audit_repository import append_event

def packages_payload(q=None): return {'status':'ok','source':'nexus-software-catalog','packages':list_packages(int(((q or {}).get('limit') or ['200'])[0]))}
def jobs_payload(q=None):
 q=q or {}; jobs=list_jobs(((q.get('status') or [None])[0]),int((q.get('limit') or ['200'])[0])); return {'status':'ok','source':'nexus-deployments','count':len(jobs),'jobs':jobs}
def job_payload(q):
 jid=(q.get('jobId') or [''])[0]
 if not jid: raise ValueError('jobId is required')
 return {'status':'ok','job':get_job(jid)}
def register_payload(data):
 for f in ('name','version'):
  if not data.get(f): raise ValueError(f'{f} is required')
 p=register_package(data); append_event({'category':'deployment','action':'software.package.registered','source':'remote-deployment','actor':{'type':'user','id':p['createdBy']},'metadata':p}); return {'status':'ok','package':p}
def create_payload(data):
 if not data.get('targets'): raise ValueError('At least one deployment target is required')
 if len(data['targets'])>1000: raise ValueError('A deployment job supports at most 1000 targets')
 j=create_job(data); append_event({'category':'deployment','action':'deployment.job.created','source':'remote-deployment','actor':{'type':'user','id':j['requestedBy']},'correlationId':j['correlationId'],'metadata':{'jobId':j['jobId'],'targetCount':len(j['targets']),'strategy':j['strategy']}}); return {'status':'ok','job':j}
def transition_payload(data):
 jid=str(data.get('jobId') or ''); action=str(data.get('action') or '')
 if not jid: raise ValueError('jobId is required')
 allowed={'approve':'approved','start':'running','succeed':'succeeded','fail':'failed','cancel':'cancelled','partial':'partial'}
 if action not in allowed: raise ValueError('Unsupported transition action')
 current=get_job(jid)
 if action in ('start','succeed','fail','partial') and not current.get('approvalId') and current['status'] not in ('approved','running'):
  raise ValueError('Deployment execution requires an approvalId or approved status')
 j=set_status(jid,allowed[action],data.get('result')); append_event({'category':'deployment','action':f'deployment.job.{allowed[action]}','source':'remote-deployment','actor':{'type':'user','id':str(data.get('actorId') or 'nexus')},'correlationId':j['correlationId'],'metadata':{'jobId':jid,'status':j['status']}}); return {'status':'ok','job':j}
