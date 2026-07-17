from psycopg.types.json import Jsonb
from backend.db.connection import get_connection, transaction

def upsert_miningcore_instance(n):
    with transaction() as c:
        with c.cursor() as cur:
            cur.execute("""INSERT INTO nexus.miningcore_instances(instance_id,name,endpoint,host,port,connected,status,health,version,pool_count,first_seen_at,last_seen_at,last_changed_at,raw_payload,updated_at)
            VALUES(%(instance_id)s,%(name)s,%(endpoint)s,%(host)s,%(port)s,%(connected)s,%(status)s,%(health)s,%(version)s,%(pool_count)s,NOW(),NOW(),NOW(),%(raw_payload)s,NOW())
            ON CONFLICT(instance_id) DO UPDATE SET name=EXCLUDED.name,endpoint=EXCLUDED.endpoint,host=EXCLUDED.host,port=EXCLUDED.port,connected=EXCLUDED.connected,status=EXCLUDED.status,health=EXCLUDED.health,version=EXCLUDED.version,pool_count=EXCLUDED.pool_count,last_seen_at=NOW(),last_changed_at=CASE WHEN (nexus.miningcore_instances.connected,nexus.miningcore_instances.status,nexus.miningcore_instances.pool_count,nexus.miningcore_instances.endpoint) IS DISTINCT FROM (EXCLUDED.connected,EXCLUDED.status,EXCLUDED.pool_count,EXCLUDED.endpoint) THEN NOW() ELSE nexus.miningcore_instances.last_changed_at END,raw_payload=EXCLUDED.raw_payload,updated_at=NOW() RETURNING *""",{**n,'raw_payload':Jsonb(n.get('raw_payload') or {})})
            return serialize(cur.fetchone())

def list_miningcore_instances():
    with get_connection() as c:
        with c.cursor() as cur:
            cur.execute('SELECT * FROM nexus.miningcore_instances ORDER BY name,instance_id')
            return [serialize(r) for r in cur.fetchall()]

def mark_stale_miningcore_instances(seconds=300):
    with transaction() as c:
        with c.cursor() as cur:
            cur.execute("UPDATE nexus.miningcore_instances SET connected=FALSE,status='offline',health='unreachable',updated_at=NOW() WHERE last_seen_at < NOW()-(%s*INTERVAL '1 second') AND status<>'offline'",(seconds,))
            return cur.rowcount

def serialize(r):
    return {'instanceId':r['instance_id'],'name':r['name'],'endpoint':r['endpoint'],'host':r['host'],'port':r['port'],'connected':r['connected'],'status':r['status'],'health':r['health'],'version':r['version'],'poolCount':r['pool_count'],'firstSeenAt':r['first_seen_at'].isoformat() if r['first_seen_at'] else None,'lastSeenAt':r['last_seen_at'].isoformat() if r['last_seen_at'] else None,'lastChangedAt':r['last_changed_at'].isoformat() if r['last_changed_at'] else None,'raw':r['raw_payload'] or {}}
