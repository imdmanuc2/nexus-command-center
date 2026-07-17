from __future__ import annotations
import hashlib,json
from typing import Any
from psycopg.types.json import Jsonb
from backend.db.connection import get_connection,transaction

def list_actions():
 with get_connection() as c:
  with c.cursor() as cur:
   cur.execute("SELECT * FROM nexus.automation_actions WHERE enabled=TRUE ORDER BY risk_level,name")
   rows=cur.fetchall()
 return [{"actionId":r["action_id"],"name":r["name"],"description":r["description"],"actionType":r["action_type"],"entityType":r["entity_type"],"riskLevel":r["risk_level"],"requiresApproval":r["requires_approval"],"supportsDryRun":r["supports_dry_run"],"timeoutSeconds":r["timeout_seconds"],"retryLimit":r["retry_limit"],"commandTemplate":r["command_template"] or {},"metadata":r["metadata"] or {}} for r in rows]

def get_action(action_id):
 return next((a for a in list_actions() if a["actionId"]==action_id),None)

def create_run(*,action_id,recommendation_id,entity_type,entity_id,requested_by,dry_run,input_payload,execution_plan,requires_approval):
 raw=json.dumps({"a":action_id,"r":recommendation_id,"t":entity_type,"e":entity_id,"u":requested_by,"i":input_payload},sort_keys=True,default=str)
 run_id='run-'+hashlib.sha256(raw.encode()).hexdigest()[:16]
 status='pending-approval' if requires_approval else 'queued'
 with transaction() as c:
  with c.cursor() as cur:
   cur.execute("""INSERT INTO nexus.automation_runs(run_id,action_id,recommendation_id,entity_type,entity_id,status,requested_by,dry_run,input_payload,execution_plan) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(run_id) DO UPDATE SET updated_at=NOW() RETURNING *""",(run_id,action_id,recommendation_id,entity_type,entity_id,status,requested_by,dry_run,Jsonb(input_payload),Jsonb(execution_plan)))
   row=cur.fetchone()
 return _serialize(row)

def list_runs(limit=100):
 with get_connection() as c:
  with c.cursor() as cur:
   cur.execute("SELECT * FROM nexus.automation_runs ORDER BY requested_at DESC LIMIT %s",(max(1,min(limit,1000)),))
   rows=cur.fetchall()
 return [_serialize(r) for r in rows]

def list_queued_runs(limit=25):
 with get_connection() as c:
  with c.cursor() as cur:
   cur.execute("SELECT * FROM nexus.automation_runs WHERE status='queued' ORDER BY requested_at LIMIT %s",(limit,))
   rows=cur.fetchall()
 return [_serialize(r) for r in rows]

def mark_run_running(run_id):
 with transaction() as c:
  with c.cursor() as cur:
   cur.execute("UPDATE nexus.automation_runs SET status='running',attempt_count=attempt_count+1,started_at=NOW(),updated_at=NOW() WHERE run_id=%s AND status='queued'",(run_id,))
   return cur.rowcount==1

def complete_run(*,run_id,status,result_payload,error_message=''):
 with transaction() as c:
  with c.cursor() as cur:
   cur.execute("UPDATE nexus.automation_runs SET status=%s,result_payload=%s,error_message=%s,completed_at=NOW(),updated_at=NOW() WHERE run_id=%s",(status,Jsonb(result_payload),error_message,run_id))

def automation_summary():
 with get_connection() as c:
  with c.cursor() as cur:
   cur.execute("""SELECT COUNT(*) FILTER(WHERE status='pending-approval') pending_approval,COUNT(*) FILTER(WHERE status='queued') queued,COUNT(*) FILTER(WHERE status='running') running,COUNT(*) FILTER(WHERE status='completed') completed,COUNT(*) FILTER(WHERE status='failed') failed FROM nexus.automation_runs""")
   r=cur.fetchone()
 return {"pendingApproval":r["pending_approval"],"queued":r["queued"],"running":r["running"],"completed":r["completed"],"failed":r["failed"]}

def _serialize(r):
 return {"runId":r["run_id"],"actionId":r["action_id"],"recommendationId":r["recommendation_id"],"entityType":r["entity_type"],"entityId":r["entity_id"],"status":r["status"],"requestedBy":r["requested_by"],"approvedBy":r["approved_by"],"dryRun":r["dry_run"],"attemptCount":r["attempt_count"],"inputPayload":r["input_payload"] or {},"executionPlan":r["execution_plan"] or {},"resultPayload":r["result_payload"] or {},"errorMessage":r["error_message"],"requestedAt":r["requested_at"].isoformat(),"approvedAt":r["approved_at"].isoformat() if r["approved_at"] else None,"startedAt":r["started_at"].isoformat() if r["started_at"] else None,"completedAt":r["completed_at"].isoformat() if r["completed_at"] else None}
