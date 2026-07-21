from uuid import uuid4
from psycopg.types.json import Jsonb
from backend.db.connection import get_connection, transaction

def _rows(sql,args=()):
    with get_connection() as c:
        with c.cursor() as cur: cur.execute(sql,args); return [dict(r) for r in cur.fetchall()]

def catalog(): return _rows("SELECT * FROM nexus.relationship_type_catalog WHERE active=TRUE ORDER BY display_name")
def for_asset(asset_id):
    return _rows("SELECT * FROM nexus.relationships WHERE status='active' AND approved=TRUE AND (source_id=%s OR target_id=%s) ORDER BY relationship_type,source_id,target_id",(asset_id,asset_id))
def workloads(asset_id): return _rows("SELECT * FROM nexus.workload_assignments WHERE asset_id=%s ORDER BY assigned_at DESC",(asset_id,))
def capability(asset_id):
    rows=_rows("SELECT * FROM nexus.compute_capabilities WHERE asset_id=%s",(asset_id,)); return rows[0] if rows else None
def upsert(data):
    rid=str(data.get('relationshipId') or f"relationship-{uuid4().hex}")
    vals=(rid,str(data.get('sourceType') or 'asset'),str(data['sourceId']),str(data['relationshipType']),str(data.get('targetType') or 'asset'),str(data['targetId']),str(data.get('status') or 'active'),data.get('confidence'),str(data.get('source') or 'cmdb'),bool(data.get('observed',False)),bool(data.get('approved',True)),Jsonb(data.get('metadata') or {}),str(data.get('criticality') or 'normal'),str(data.get('redundancyGroup') or ''),str(data.get('verificationStatus') or 'unverified'),str(data.get('changedBy') or 'cmdb-user'))
    with transaction() as c:
      with c.cursor() as cur:
       cur.execute("""INSERT INTO nexus.relationships(relationship_id,source_type,source_id,relationship_type,target_type,target_id,status,confidence,source,observed,approved,metadata,criticality,redundancy_group,verification_status,created_by,updated_by) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(source_type,source_id,relationship_type,target_type,target_id) DO UPDATE SET status=EXCLUDED.status,confidence=EXCLUDED.confidence,source=EXCLUDED.source,observed=EXCLUDED.observed,approved=EXCLUDED.approved,metadata=EXCLUDED.metadata,criticality=EXCLUDED.criticality,redundancy_group=EXCLUDED.redundancy_group,verification_status=EXCLUDED.verification_status,updated_by=EXCLUDED.updated_by,last_seen_at=NOW(),updated_at=NOW() RETURNING *""",vals); row=dict(cur.fetchone());
       cur.execute("INSERT INTO nexus.relationship_history(history_id,relationship_id,action,after_state,reason,changed_by,source,correlation_id) VALUES(%s,%s,'upsert',%s,%s,%s,%s,%s)",(f'history-{uuid4().hex}',row['relationship_id'],Jsonb(row),str(data.get('reason') or ''),vals[-1],vals[8],str(data.get('correlationId') or '')))
       return row
def map_asset(asset_id,depth=3):
    rels=_rows("SELECT * FROM nexus.relationships WHERE status='active' AND approved=TRUE")
    nodes={asset_id}; edges=[]; frontier={asset_id}
    for _ in range(max(1,min(depth,8))):
      nxt=set()
      for r in rels:
       if r['source_id'] in frontier or r['target_id'] in frontier:
        edges.append(r); nxt|={r['source_id'],r['target_id']}
      nxt-=nodes
      if not nxt: break
      nodes|=nxt; frontier=nxt
    return {'rootAssetId':asset_id,'nodes':sorted(nodes),'relationships':edges,'blastRadius':len(nodes)-1}
