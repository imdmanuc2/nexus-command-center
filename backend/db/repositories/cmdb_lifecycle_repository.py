from __future__ import annotations
from typing import Any
from uuid import uuid4
from psycopg.types.json import Jsonb
from backend.db.connection import get_connection, transaction
from backend.db.repositories.operational_state_repository import VALID_STATES, set_asset_state

VALID_LIFECYCLE = {'managed','discovered','imported','virtual','decommissioning','retired'}
VALID_DESIRED = {'online','offline'}

def _row(row):
    return {'assetId':row['asset_id'],'assetType':row['asset_type'],'assetName':row['display_name'] or row['name'],
      'lifecycleStatus':row['lifecycle_status'],'operationalState':row['operational_state'],
      'desiredOperationalState':row['desired_operational_state'],'operationalStateReason':row['operational_state_reason'],
      'commissionedAt':row['commissioned_at'].isoformat() if row['commissioned_at'] else None,
      'inServiceAt':row['in_service_at'].isoformat() if row['in_service_at'] else None,
      'decommissionedAt':row['decommissioned_at'].isoformat() if row['decommissioned_at'] else None,
      'retiredAt':row['retired_at'].isoformat() if row['retired_at'] else None}

def get(asset_id):
    with get_connection() as c:
      with c.cursor() as cur:
       cur.execute('''SELECT asset_id,asset_type,name,display_name,lifecycle_status,operational_state,
       desired_operational_state,operational_state_reason,commissioned_at,in_service_at,decommissioned_at,retired_at
       FROM nexus.assets WHERE asset_id=%s''',(asset_id,)); r=cur.fetchone()
    if not r: raise KeyError('Asset not found')
    return _row(r)

def update(asset_id:str, data:dict[str,Any]):
    actor=str(data.get('changedBy') or 'nexus'); reason=str(data.get('reason') or '').strip(); source=str(data.get('source') or 'cmdb')
    corr=str(data.get('correlationId') or f'corr-{uuid4().hex}')
    before=get(asset_id)
    op=data.get('operationalState')
    if op is not None:
      if str(op).lower() not in VALID_STATES: raise ValueError('Unsupported operational state')
      set_asset_state(asset_id,str(op).lower(),reason=reason,changed_by=actor,source=source,correlation_id=corr)
    lifecycle=data.get('lifecycleStatus'); desired=data.get('desiredOperationalState')
    if lifecycle is not None and str(lifecycle).lower() not in VALID_LIFECYCLE: raise ValueError('Unsupported lifecycle status')
    if desired is not None and str(desired).lower() not in VALID_DESIRED: raise ValueError('Unsupported desired state')
    fields={k:v for k,v in {
      'lifecycle_status':str(lifecycle).lower() if lifecycle is not None else None,
      'desired_operational_state':str(desired).lower() if desired is not None else None,
      'commissioned_at':data.get('commissionedAt'),'in_service_at':data.get('inServiceAt'),
      'decommissioned_at':data.get('decommissionedAt')}.items() if v is not None}
    if fields:
      with transaction() as c:
       with c.cursor() as cur:
        for col,val in fields.items():
         old={'lifecycle_status':before['lifecycleStatus'],'desired_operational_state':before['desiredOperationalState'],
              'commissioned_at':before['commissionedAt'],'in_service_at':before['inServiceAt'],'decommissioned_at':before['decommissionedAt']}[col]
         if str(old or '')==str(val or ''): continue
         cur.execute(f'UPDATE nexus.assets SET {col}=%s, updated_at=NOW() WHERE asset_id=%s',(val,asset_id))
         cur.execute('''INSERT INTO nexus.asset_lifecycle_history(asset_id,event_type,field_name,previous_value,new_value,reason,changed_by,source,correlation_id,metadata)
         VALUES(%s,'field_changed',%s,%s,%s,%s,%s,%s,%s,%s)''',(asset_id,col,str(old) if old is not None else None,str(val),reason,actor,source,corr,Jsonb({})))
    return get(asset_id)

def history(asset_id,limit=100):
    with get_connection() as c:
     with c.cursor() as cur:
      cur.execute('''SELECT history_id,event_type,field_name,previous_value,new_value,reason,changed_by,source,correlation_id,metadata,changed_at
      FROM nexus.asset_lifecycle_history WHERE asset_id=%s ORDER BY changed_at DESC LIMIT %s''',(asset_id,max(1,min(int(limit),500)))); rows=cur.fetchall()
    return [{'historyId':r['history_id'],'eventType':r['event_type'],'fieldName':r['field_name'],'previousValue':r['previous_value'],'newValue':r['new_value'],'reason':r['reason'],'changedBy':r['changed_by'],'source':r['source'],'correlationId':r['correlation_id'],'metadata':r['metadata'] or {},'changedAt':r['changed_at'].isoformat()} for r in rows]
