from __future__ import annotations
from typing import Any
from psycopg.types.json import Jsonb
from backend.db.connection import get_connection, transaction

def _event(cur, rid, etype, atype, aid, msg, data=None):
    cur.execute("""INSERT INTO nexus.change_rollback_events
      (rollback_id,event_type,actor_type,actor_id,message,event_data)
      VALUES(%s,%s,%s,%s,%s,%s)""", (rid,etype,atype,aid or '',msg,Jsonb(data or {})))

def create_plan(payload: dict[str, Any]):
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO nexus.change_rollback_plans
              (change_id,source_operation_id,rollback_action,target_type,target_id,asset_id,parameters,reason,requested_by)
              VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
              (payload['changeId'],payload.get('sourceOperationId'),payload['rollbackAction'],payload['targetType'],payload['targetId'],payload.get('assetId'),Jsonb(payload.get('parameters') or {}),payload.get('reason',''),payload.get('requestedBy','')))
            row=dict(cur.fetchone())
            cur.execute("""UPDATE nexus.change_requests SET active_rollback_id=%s,recovery_status='rollback_planned',rollback_status='planned',updated_at=NOW() WHERE change_id=%s""",(row['rollback_id'],row['change_id']))
            _event(cur,row['rollback_id'],'created','user',payload.get('requestedBy',''),'Rollback plan created.',{})
            return row

def approve_plan(rid, approved_by):
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("""UPDATE nexus.change_rollback_plans SET approval_status='approved',status='approved',approved_by=%s,approved_at=NOW(),updated_at=NOW() WHERE rollback_id=%s AND status='draft' RETURNING *""",(approved_by,rid))
            row=cur.fetchone()
            if not row: return None
            _event(cur,rid,'approved','user',approved_by,'Rollback approved.',{})
            return dict(row)

def queue_plan(rid, requested_by=''):
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("""UPDATE nexus.change_rollback_plans SET status='queued',requested_at=NOW(),updated_at=NOW() WHERE rollback_id=%s AND approval_status IN ('approved','not_required') AND status IN ('approved','draft') RETURNING *""",(rid,))
            row=cur.fetchone()
            if not row: return None
            row=dict(row)
            cur.execute("UPDATE nexus.change_requests SET recovery_status='rollback_queued',rollback_status='queued',updated_at=NOW() WHERE change_id=%s",(row['change_id'],))
            _event(cur,rid,'queued','user',requested_by,'Rollback queued.',{})
            return row

def claim_next(worker_id, lease_seconds=180):
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT rollback_id FROM nexus.change_rollback_plans WHERE status='queued' AND approval_status IN ('approved','not_required') AND (lease_expires_at IS NULL OR lease_expires_at<NOW()) ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1""")
            row=cur.fetchone()
            if not row: return None
            cur.execute("""UPDATE nexus.change_rollback_plans SET status='running',claimed_by=%s,lease_expires_at=NOW()+(%s||' seconds')::interval,updated_at=NOW() WHERE rollback_id=%s RETURNING *""",(worker_id,int(lease_seconds),row['rollback_id']))
            plan=dict(cur.fetchone())
            cur.execute("UPDATE nexus.change_requests SET recovery_status='rollback_running',rollback_status='running',updated_at=NOW() WHERE change_id=%s",(plan['change_id'],))
            _event(cur,plan['rollback_id'],'claimed','worker',worker_id,'Rollback claimed.',{'leaseSeconds':lease_seconds})
            return plan

def start_attempt(plan, worker_id):
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*)+1 AS n FROM nexus.change_rollback_attempts WHERE rollback_id=%s",(plan['rollback_id'],)); n=int(cur.fetchone()['n'])
            cur.execute("""INSERT INTO nexus.change_rollback_attempts (rollback_id,worker_id,attempt_number,status,capability) VALUES(%s,%s,%s,'running',%s) RETURNING attempt_id""",(plan['rollback_id'],worker_id,n,plan['rollback_action']))
            return str(cur.fetchone()['attempt_id'])

def finish_success(aid, plan, result, verification):
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("""UPDATE nexus.change_rollback_attempts SET status='succeeded',completed_at=NOW(),duration_ms=%s,exit_code=%s,timed_out=%s,transport=%s,stdout=%s,stderr=%s,result_data=%s,verification_data=%s WHERE attempt_id=%s""",(result.get('durationMs'),result.get('exitCode'),bool(result.get('timedOut')),result.get('transport',''),result.get('stdout',''),result.get('stderr',''),Jsonb(result),Jsonb(verification or {}),aid))
            cur.execute("""UPDATE nexus.change_rollback_plans SET status='succeeded',verification_status='passed',recovery_status='recovered',result_data=%s,error_message='',lease_expires_at=NULL,completed_at=NOW(),updated_at=NOW() WHERE rollback_id=%s""",(Jsonb({'execution':result,'verification':verification or {}}),plan['rollback_id']))
            cur.execute("UPDATE nexus.change_requests SET status='rolled-back',recovery_status='recovered',rollback_status='succeeded',recovered_at=NOW(),updated_at=NOW() WHERE change_id=%s",(plan['change_id'],))
            _event(cur,plan['rollback_id'],'succeeded','worker',plan.get('claimed_by',''),'Rollback completed and verified.',{})

def finish_failure(aid, plan, error, result=None):
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE nexus.change_rollback_attempts SET status='failed',completed_at=NOW(),error_message=%s,result_data=%s WHERE attempt_id=%s",(error,Jsonb(result or {}),aid))
            cur.execute("""UPDATE nexus.change_rollback_plans SET status='manual_intervention',verification_status='failed',recovery_status='manual_intervention',error_message=%s,result_data=%s,lease_expires_at=NULL,completed_at=NOW(),updated_at=NOW() WHERE rollback_id=%s""",(error,Jsonb(result or {}),plan['rollback_id']))
            cur.execute("UPDATE nexus.change_requests SET recovery_status='manual_intervention',rollback_status='failed',updated_at=NOW() WHERE change_id=%s",(plan['change_id'],))
            _event(cur,plan['rollback_id'],'failed','worker',plan.get('claimed_by',''),'Rollback failed.',{'error':error})

def reconcile_stale(stale_seconds=300):
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("""UPDATE nexus.change_rollback_plans SET status='queued',claimed_by='',lease_expires_at=NULL,error_message='Recovered stale worker lease.',updated_at=NOW() WHERE status='running' AND lease_expires_at<NOW() AND updated_at<NOW()-(%s||' seconds')::interval RETURNING rollback_id""",(int(stale_seconds),))
            return [str(r['rollback_id']) for r in cur.fetchall()]

def status():
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status,COUNT(*) AS count FROM nexus.change_rollback_plans GROUP BY status ORDER BY status")
            counts=[dict(r) for r in cur.fetchall()]
            return {'counts':counts,'manualInterventionCount':sum(int(r['count']) for r in counts if r['status']=='manual_intervention')}

def history(limit=100):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""SELECT p.*,COALESCE((SELECT jsonb_agg(to_jsonb(a) ORDER BY a.started_at DESC) FROM nexus.change_rollback_attempts a WHERE a.rollback_id=p.rollback_id),'[]'::jsonb) AS attempts FROM nexus.change_rollback_plans p ORDER BY p.created_at DESC LIMIT %s""",(max(1,min(int(limit),500)),))
            return [dict(r) for r in cur.fetchall()]
