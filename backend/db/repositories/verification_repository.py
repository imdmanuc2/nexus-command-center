from __future__ import annotations
from psycopg.types.json import Jsonb
from backend.db.connection import get_connection, transaction

def event(cur, run_id, kind, actor, message, details=None):
    cur.execute("""INSERT INTO nexus.verification_events(run_id,event_type,actor,message,details)
                   VALUES(%s,%s,%s,%s,%s)""",
                (run_id,kind,actor,message,Jsonb(details or {})))

def profiles():
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""SELECT p.*,COALESCE(
          (SELECT jsonb_agg(to_jsonb(s) ORDER BY s.position)
             FROM nexus.verification_profile_steps s WHERE s.profile_id=p.profile_id),
          '[]'::jsonb) AS steps
          FROM nexus.verification_profiles p ORDER BY p.profile_key""")
        return [dict(r) for r in cur.fetchall()]

def create_profile(data):
    steps=list(data.get("steps") or [])
    with transaction() as conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO nexus.verification_profiles
          (profile_key,name,description,target_type,enabled,rollback_on_failure,
           minimum_score,metadata,created_by)
          VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
          (str(data["profileKey"]),str(data["name"]),str(data.get("description") or ""),
           str(data.get("targetType") or "asset"),bool(data.get("enabled",True)),
           bool(data.get("rollbackOnFailure",False)),float(data.get("minimumScore",100)),
           Jsonb(data.get("metadata") or {}),str(data.get("createdBy") or "operator")))
        profile=dict(cur.fetchone())
        for pos,step in enumerate(steps,1):
            cur.execute("""INSERT INTO nexus.verification_profile_steps
              (profile_id,position,name,verifier_type,required,timeout_seconds,weight,configuration,expected)
              VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
              (profile["profile_id"],int(step.get("position") or pos),str(step["name"]),
               str(step["verifierType"]),bool(step.get("required",True)),
               int(step.get("timeoutSeconds") or 30),float(step.get("weight") or 1),
               Jsonb(step.get("configuration") or {}),Jsonb(step.get("expected") or {})))
        return profile

def queue(data):
    key=str(data["profileKey"])
    with transaction() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM nexus.verification_profiles WHERE profile_key=%s AND enabled=TRUE",(key,))
        profile=cur.fetchone()
        if not profile:
            raise ValueError(f"Unknown or disabled verification profile: {key}")
        cur.execute("""INSERT INTO nexus.verification_runs
          (profile_id,profile_key,change_id,rollback_id,target_type,target_id,asset_id,
           transport,parameters,context,requested_by)
          VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
          (profile["profile_id"],key,data.get("changeId"),data.get("rollbackId"),
           str(data.get("targetType") or "asset"),str(data["targetId"]),data.get("assetId"),
           str(data.get("transport") or "local"),Jsonb(data.get("parameters") or {}),
           Jsonb(data.get("context") or {}),str(data.get("requestedBy") or "operator")))
        run=dict(cur.fetchone())
        cur.execute("""INSERT INTO nexus.verification_step_runs
          (run_id,step_id,position,name,verifier_type,required,weight,expected)
          SELECT %s,step_id,position,name,verifier_type,required,weight,expected
          FROM nexus.verification_profile_steps WHERE profile_id=%s ORDER BY position""",
          (run["run_id"],profile["profile_id"]))
        event(cur,run["run_id"],"queued",run["requested_by"],"Verification run queued.",{"profileKey":key})
        return run

def claim(worker_id, lease_seconds=120):
    with transaction() as conn, conn.cursor() as cur:
        cur.execute("""SELECT * FROM nexus.verification_runs WHERE status='queued'
                       ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1""")
        row=cur.fetchone()
        if not row: return None
        cur.execute("""UPDATE nexus.verification_runs SET status='running',claimed_by=%s,
          started_at=COALESCE(started_at,NOW()),
          lease_expires_at=NOW()+(%s||' seconds')::interval,updated_at=NOW()
          WHERE run_id=%s RETURNING *""",(worker_id,int(lease_seconds),row["run_id"]))
        run=dict(cur.fetchone())
        event(cur,run["run_id"],"claimed",worker_id,"Verification run claimed.",{})
        return run

def steps(run_id):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""SELECT sr.*,ps.configuration,ps.timeout_seconds
          FROM nexus.verification_step_runs sr
          LEFT JOIN nexus.verification_profile_steps ps ON ps.step_id=sr.step_id
          WHERE sr.run_id=%s ORDER BY sr.position""",(run_id,))
        return [dict(r) for r in cur.fetchall()]

def start_step(step_run_id):
    with transaction() as conn, conn.cursor() as cur:
        cur.execute("UPDATE nexus.verification_step_runs SET status='running',started_at=NOW() WHERE step_run_id=%s",(step_run_id,))

def finish_step(step_run_id,passed,result,error=""):
    status="passed" if passed else "failed"
    with transaction() as conn, conn.cursor() as cur:
        cur.execute("""UPDATE nexus.verification_step_runs SET status=%s,actual=%s,result_data=%s,
          error_message=%s,duration_ms=%s,completed_at=NOW()
          WHERE step_run_id=%s RETURNING run_id""",
          (status,Jsonb({"passed":passed}),Jsonb(result or {}),error,(result or {}).get("durationMs"),step_run_id))
        run_id=cur.fetchone()["run_id"]
        cur.execute("""INSERT INTO nexus.verification_evidence
          (run_id,step_run_id,evidence_type,content,stdout,stderr,exit_code,timed_out)
          VALUES(%s,%s,%s,%s,%s,%s,%s,%s)""",
          (run_id,step_run_id,str((result or {}).get("evidenceType") or "result"),
           Jsonb(result or {}),str((result or {}).get("stdout") or ""),
           str((result or {}).get("stderr") or ""),(result or {}).get("exitCode"),
           bool((result or {}).get("timedOut",False))))

def finish_run(run,passed,score,summary,error=""):
    status="passed" if passed else "failed"
    with transaction() as conn, conn.cursor() as cur:
        cur.execute("""UPDATE nexus.verification_runs SET status=%s,result=%s,score=%s,summary=%s,
          error_message=%s,rollback_recommended=%s,lease_expires_at=NULL,
          completed_at=NOW(),updated_at=NOW() WHERE run_id=%s""",
          (status,status,score,Jsonb(summary),error,bool(summary.get("rollbackRecommended")),run["run_id"]))
        if run.get("change_id"):
            if passed:
                cur.execute("""UPDATE nexus.change_requests SET status='completed',
                  verification_status='passed',completed_at=COALESCE(completed_at,NOW()),updated_at=NOW()
                  WHERE change_id=%s AND status IN ('executing','completed')""",(run["change_id"],))
            else:
                cur.execute("""UPDATE nexus.change_requests SET status='failed',
                  verification_status='failed',failure_reason=%s,updated_at=NOW()
                  WHERE change_id=%s AND status IN ('executing','completed')""",
                  (error or "Post-change verification failed.",run["change_id"]))
        event(cur,run["run_id"],status,run.get("claimed_by") or "worker",f"Verification run {status}.",summary)

def reconcile(stale_seconds=180):
    with transaction() as conn, conn.cursor() as cur:
        cur.execute("""UPDATE nexus.verification_runs SET status='queued',claimed_by='',
          lease_expires_at=NULL,error_message='Recovered stale verification lease.',updated_at=NOW()
          WHERE status='running' AND lease_expires_at<NOW()
          AND updated_at<NOW()-(%s||' seconds')::interval RETURNING run_id""",(int(stale_seconds),))
        return [str(r["run_id"]) for r in cur.fetchall()]

def get(run_id):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("""SELECT r.*,
          COALESCE((SELECT jsonb_agg(to_jsonb(s) ORDER BY s.position)
          FROM nexus.verification_step_runs s WHERE s.run_id=r.run_id),'[]'::jsonb) steps,
          COALESCE((SELECT jsonb_agg(to_jsonb(e) ORDER BY e.collected_at)
          FROM nexus.verification_evidence e WHERE e.run_id=r.run_id),'[]'::jsonb) evidence,
          COALESCE((SELECT jsonb_agg(to_jsonb(v) ORDER BY v.occurred_at)
          FROM nexus.verification_events v WHERE v.run_id=r.run_id),'[]'::jsonb) events
          FROM nexus.verification_runs r WHERE r.run_id=%s""",(run_id,))
        row=cur.fetchone(); return dict(row) if row else None

def runs(limit=100):
    with get_connection() as conn, conn.cursor() as cur:
        cur.execute("SELECT * FROM nexus.verification_runs ORDER BY created_at DESC LIMIT %s",
                    (max(1,min(int(limit),500)),))
        return [dict(r) for r in cur.fetchall()]
