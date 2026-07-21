from __future__ import annotations
from uuid import uuid4
from typing import Any
from psycopg.types.json import Jsonb
from backend.db.connection import get_connection

def _iso(v): return v.isoformat() if v else None

def register_package(data: dict[str,Any]):
    pid=str(data.get('packageId') or f"software-{uuid4().hex}")
    with get_connection() as c:
      with c.cursor() as cur:
       cur.execute("""INSERT INTO nexus.software_packages(package_id,name,version,package_type,source_uri,checksum_sha256,metadata,created_by)
       VALUES(%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(name,version) DO UPDATE SET source_uri=EXCLUDED.source_uri,checksum_sha256=EXCLUDED.checksum_sha256,metadata=EXCLUDED.metadata RETURNING *""",
       (pid,str(data['name']),str(data['version']),str(data.get('packageType') or 'application'),str(data.get('sourceUri') or ''),str(data.get('checksumSha256') or ''),Jsonb(data.get('metadata') or {}),str(data.get('createdBy') or 'nexus')))
       r=cur.fetchone(); c.commit(); return _package(r)

def list_packages(limit=200):
 with get_connection() as c:
  with c.cursor() as cur:
   cur.execute("SELECT * FROM nexus.software_packages ORDER BY created_at DESC LIMIT %s",(max(1,min(int(limit),1000)),)); return [_package(r) for r in cur.fetchall()]

def _package(r): return {'packageId':r['package_id'],'name':r['name'],'version':r['version'],'packageType':r['package_type'],'sourceUri':r['source_uri'],'checksumSha256':r['checksum_sha256'],'metadata':r['metadata'] or {},'createdAt':_iso(r['created_at']),'createdBy':r['created_by']}

def create_job(data):
 jid=str(data.get('jobId') or f"deploy-{uuid4().hex}"); corr=str(data.get('correlationId') or f"corr-{uuid4().hex}")
 targets=data.get('targets') or []
 with get_connection() as c:
  with c.cursor() as cur:
   cur.execute("""INSERT INTO nexus.deployment_jobs(job_id,package_id,name,deployment_type,status,strategy,requested_by,approval_id,correlation_id,parameters)
   VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",(jid,data.get('packageId'),str(data.get('name') or 'Remote deployment'),str(data.get('deploymentType') or 'software'),str(data.get('status') or 'queued'),str(data.get('strategy') or 'rolling'),str(data.get('requestedBy') or 'nexus'),data.get('approvalId'),corr,Jsonb(data.get('parameters') or {})))
   row=cur.fetchone()
   for t in targets:
    cur.execute("""INSERT INTO nexus.deployment_targets(job_id,target_asset_id,target_asset_type,current_version,desired_version)
    VALUES(%s,%s,%s,%s,%s)""",(jid,str(t['assetId']),str(t.get('assetType') or 'asset'),str(t.get('currentVersion') or ''),str(t.get('desiredVersion') or '')))
   c.commit()
 return get_job(jid)

def list_jobs(status=None,limit=200):
 q='SELECT * FROM nexus.deployment_jobs'; vals=[]
 if status: q+=' WHERE status=%s'; vals.append(status)
 q+=' ORDER BY requested_at DESC LIMIT %s'; vals.append(max(1,min(int(limit),1000)))
 with get_connection() as c:
  with c.cursor() as cur: cur.execute(q,vals); rows=cur.fetchall()
 return [_job(r,[]) for r in rows]

def get_job(jid):
 with get_connection() as c:
  with c.cursor() as cur:
   cur.execute('SELECT * FROM nexus.deployment_jobs WHERE job_id=%s',(jid,)); r=cur.fetchone()
   if not r: raise ValueError('Deployment job not found')
   cur.execute('SELECT * FROM nexus.deployment_targets WHERE job_id=%s ORDER BY target_id',(jid,)); ts=cur.fetchall()
 return _job(r,[{'targetId':t['target_id'],'assetId':t['target_asset_id'],'assetType':t['target_asset_type'],'status':t['status'],'currentVersion':t['current_version'],'desiredVersion':t['desired_version'],'startedAt':_iso(t['started_at']),'completedAt':_iso(t['completed_at']),'result':t['result'] or {}} for t in ts])

def set_status(jid,status,result=None):
 fields=['status=%s']; vals=[status]
 if status=='running': fields.append('started_at=COALESCE(started_at,now())')
 if status in ('succeeded','failed','cancelled','partial'): fields.append('completed_at=now()')
 if result is not None: fields.append('result=%s'); vals.append(Jsonb(result))
 vals.append(jid)
 with get_connection() as c:
  with c.cursor() as cur:
   cur.execute(f"UPDATE nexus.deployment_jobs SET {','.join(fields)} WHERE job_id=%s",vals)
   if cur.rowcount!=1: raise ValueError('Deployment job not found')
  c.commit()
 return get_job(jid)

def _job(r,targets): return {'jobId':r['job_id'],'packageId':r['package_id'],'name':r['name'],'deploymentType':r['deployment_type'],'status':r['status'],'strategy':r['strategy'],'requestedBy':r['requested_by'],'requestedAt':_iso(r['requested_at']),'startedAt':_iso(r['started_at']),'completedAt':_iso(r['completed_at']),'approvalId':r['approval_id'],'correlationId':r['correlation_id'],'parameters':r['parameters'] or {},'result':r['result'] or {},'targets':targets}
