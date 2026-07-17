from backend.db.repositories.miningcore_repository import upsert_miningcore_instance,mark_stale_miningcore_instances
from backend.services.resource_sync_common import fetch_json,parse_endpoint,stable_id

def synchronize_miningcore_instances(stale_seconds=300):
    payload=fetch_json('/api/connectors/status'); instances=((payload.get('connectors') or {}).get('miningcore') or {}).get('instances') or []; rows=[]
    for raw in instances:
        endpoint=str(raw.get('endpoint') or ''); host,port=parse_endpoint(endpoint); host=str(raw.get('host') or host); name=str(raw.get('name') or host or endpoint or 'MiningCore'); connected=bool(raw.get('connected'))
        rows.append(upsert_miningcore_instance({'instance_id':str(raw.get('instanceId') or raw.get('id') or stable_id('miningcore',endpoint,host,name)),'name':name,'endpoint':endpoint,'host':host,'port':raw.get('port') or port,'connected':connected,'status':'online' if connected else 'offline','health':'healthy' if connected else 'unreachable','version':str(raw.get('version') or ''),'pool_count':int(raw.get('poolCount') or 0),'raw_payload':raw}))
    return {'status':'ok','observed':len(rows),'written':len(rows),'markedOffline':mark_stale_miningcore_instances(stale_seconds),'instances':rows}
