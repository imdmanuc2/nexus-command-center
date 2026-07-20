from __future__ import annotations
import hashlib, json
from psycopg.types.json import Jsonb
from backend.db.connection import get_connection, transaction

def sync_catalog(items):
    with transaction() as conn:
        with conn.cursor() as cur:
            for item in items:
                definition=json.dumps(item, sort_keys=True, default=str)
                digest=hashlib.sha256(definition.encode()).hexdigest()
                cur.execute("""INSERT INTO nexus.playbooks(playbook_id,name,description,category,risk_level,current_version,source_path)
                VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(playbook_id) DO UPDATE SET name=EXCLUDED.name,description=EXCLUDED.description,category=EXCLUDED.category,risk_level=EXCLUDED.risk_level,current_version=EXCLUDED.current_version,source_path=EXCLUDED.source_path,updated_at=NOW()""",
                (item['playbookId'],item['name'],item['description'],item['category'],item['riskLevel'],item['version'],item['sourcePath']))
                cur.execute("""INSERT INTO nexus.playbook_versions(playbook_id,version,definition,definition_hash)
                VALUES(%s,%s,%s,%s) ON CONFLICT(playbook_id,version) DO UPDATE SET definition=EXCLUDED.definition,definition_hash=EXCLUDED.definition_hash""",
                (item['playbookId'],item['version'],Jsonb(item),digest))

def create_run(run):
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO nexus.playbook_runs(run_id,playbook_id,playbook_version,operation_session_id,target_asset_id,target_type,status,requested_by,variables,started_at)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW()) RETURNING *""",
            (run['runId'],run['playbookId'],run['playbookVersion'],run.get('operationSessionId'),run.get('targetAssetId'),run.get('targetType'),run['status'],run.get('requestedBy','nexus-user'),Jsonb(run.get('variables',{}))))
            return dict(cur.fetchone())
def add_step(run_id, step, position, parameters):
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO nexus.playbook_steps(run_id,step_id,position,capability,status,parameters,started_at)
            VALUES(%s,%s,%s,%s,'running',%s,NOW()) RETURNING step_run_id""",(run_id,step.step_id,position,step.capability,Jsonb(parameters)))
            return cur.fetchone()['step_run_id']
def finish_step(step_run_id,status,result=None,error=None):
    with transaction() as conn:
        with conn.cursor() as cur: cur.execute("UPDATE nexus.playbook_steps SET status=%s,result=%s,error_message=%s,completed_at=NOW() WHERE step_run_id=%s",(status,Jsonb(result or {}),error,step_run_id))
def finish_run(run_id,status,result=None,error=None):
    with transaction() as conn:
        with conn.cursor() as cur: cur.execute("UPDATE nexus.playbook_runs SET status=%s,result=%s,error_message=%s,completed_at=NOW(),updated_at=NOW() WHERE run_id=%s",(status,Jsonb(result or {}),error,run_id))
def list_runs(limit=100):
    with get_connection() as conn:
        with conn.cursor() as cur: cur.execute("SELECT * FROM nexus.playbook_runs ORDER BY created_at DESC LIMIT %s",(max(1,min(int(limit),500)),)); rows=cur.fetchall()
    return [dict(r) for r in rows]
def get_run(run_id):
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM nexus.playbook_runs WHERE run_id=%s",(run_id,)); run=cur.fetchone()
            if not run:return None
            cur.execute("SELECT * FROM nexus.playbook_steps WHERE run_id=%s ORDER BY position",(run_id,)); steps=cur.fetchall()
    result=dict(run); result['steps']=[dict(s) for s in steps]; return result
