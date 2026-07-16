"""PostgreSQL repository for workers reconciled by source identity."""
from __future__ import annotations
from typing import Any
from psycopg.types.json import Jsonb
from backend.db.connection import get_connection,transaction
from backend.db.repositories.identity_reconciliation_repository import record_identity_reconciliation

def upsert_worker(worker:dict[str,Any])->dict[str,Any]:
    incoming_id=str(worker.get('workerId') or worker.get('id') or '').strip()
    if not incoming_id: raise ValueError('Worker requires workerId or id.')
    source_system=str(worker.get('sourceSystem') or 'miningcore').strip()
    source_worker_id=str(worker.get('sourceWorkerId') or incoming_id).strip()
    if not source_system or not source_worker_id: raise ValueError('Worker requires source identity.')
    v={
      'worker_id':incoming_id,'worker_type':str(worker.get('workerType') or 'unknown').lower(),
      'hardware_type':str(worker.get('hardwareType') or ''),'display_name':str(worker.get('displayName') or worker.get('name') or incoming_id),
      'asset_id':worker.get('assetId') or None,'asset_matched':bool(worker.get('assetMatched',bool(worker.get('assetId')))),
      'reconciliation_status':str(worker.get('reconciliationStatus') or ('matched' if worker.get('assetId') else 'unmatched')),
      'pool_id':worker.get('nativePoolId') or worker.get('poolId') or None,'pool_instance_id':worker.get('poolInstanceId') or None,
      'native_pool_id':str(worker.get('nativePoolId') or worker.get('poolId') or ''),'pool_host':str(worker.get('poolHost') or ''),
      'pool_api_port':worker.get('poolApiPort'),'worker_name':str(worker.get('workerName') or worker.get('name') or ''),
      'miner_address':str(worker.get('minerAddress') or ''),'coin':worker.get('coin'),'status':str(worker.get('status') or 'unknown'),
      'current_hashrate':worker.get('currentHashrate') if worker.get('currentHashrate') is not None else worker.get('hashrate'),
      'hashrate_unit':str(worker.get('hashrateUnit') or 'H/s'),'shares_per_second':worker.get('sharesPerSecond'),
      'accepted_shares':worker.get('acceptedShares'),'rejected_shares':worker.get('rejectedShares'),'last_share_at':worker.get('lastShareAt'),
      'source_system':source_system,'source_worker_id':source_worker_id,'classification_source':str(worker.get('classificationSource') or ''),
      'classification_confidence':worker.get('classificationConfidence'),'identity':Jsonb(worker.get('identity') or {}),
      'observed_state':Jsonb(worker.get('observedState') or {}),'metadata':Jsonb(worker.get('metadata') or {})}
    with transaction() as connection:
      with connection.cursor() as cursor:
        cursor.execute('SELECT worker_id FROM nexus.workers WHERE source_system=%s AND source_worker_id=%s FOR UPDATE',(source_system,source_worker_id))
        existing=cursor.fetchone()
        if existing:
          canonical=existing['worker_id']
          cursor.execute("""
            UPDATE nexus.workers SET
              worker_type=%(worker_type)s,hardware_type=%(hardware_type)s,display_name=%(display_name)s,
              asset_id=%(asset_id)s,asset_matched=%(asset_matched)s,reconciliation_status=%(reconciliation_status)s,
              pool_id=%(pool_id)s,pool_instance_id=%(pool_instance_id)s,native_pool_id=%(native_pool_id)s,
              pool_host=%(pool_host)s,pool_api_port=%(pool_api_port)s,worker_name=%(worker_name)s,
              miner_address=%(miner_address)s,coin=%(coin)s,status=%(status)s,current_hashrate=%(current_hashrate)s,
              hashrate_unit=%(hashrate_unit)s,shares_per_second=%(shares_per_second)s,accepted_shares=%(accepted_shares)s,
              rejected_shares=%(rejected_shares)s,last_share_at=%(last_share_at)s::TIMESTAMPTZ,
              classification_source=%(classification_source)s,classification_confidence=%(classification_confidence)s,
              identity=%(identity)s,observed_state=%(observed_state)s,metadata=%(metadata)s,last_seen_at=NOW(),updated_at=NOW()
            WHERE worker_id=%(canonical)s RETURNING *
          """,{**v,'canonical':canonical});row=cursor.fetchone();action='reconciled-existing'
        else:
          cursor.execute("""
            INSERT INTO nexus.workers(worker_id,worker_type,hardware_type,display_name,asset_id,asset_matched,
            reconciliation_status,pool_id,pool_instance_id,native_pool_id,pool_host,pool_api_port,worker_name,
            miner_address,coin,status,current_hashrate,hashrate_unit,shares_per_second,accepted_shares,rejected_shares,
            last_share_at,source_system,source_worker_id,classification_source,classification_confidence,identity,
            observed_state,metadata,first_seen_at,last_seen_at,created_at,updated_at)
            VALUES(%(worker_id)s,%(worker_type)s,%(hardware_type)s,%(display_name)s,%(asset_id)s,%(asset_matched)s,
            %(reconciliation_status)s,%(pool_id)s,%(pool_instance_id)s,%(native_pool_id)s,%(pool_host)s,%(pool_api_port)s,
            %(worker_name)s,%(miner_address)s,%(coin)s,%(status)s,%(current_hashrate)s,%(hashrate_unit)s,
            %(shares_per_second)s,%(accepted_shares)s,%(rejected_shares)s,%(last_share_at)s::TIMESTAMPTZ,
            %(source_system)s,%(source_worker_id)s,%(classification_source)s,%(classification_confidence)s,
            %(identity)s,%(observed_state)s,%(metadata)s,NOW(),NOW(),NOW(),NOW()) RETURNING *
          """,v);row=cursor.fetchone();canonical=row['worker_id'];action='inserted-new'
    record_identity_reconciliation(entity_type='worker',canonical_key=f'{source_system}:{source_worker_id}',canonical_id=canonical,incoming_id=incoming_id,source_system=source_system,source_identity=source_worker_id,action=action,details={'assetId':v['asset_id'],'poolInstanceId':v['pool_instance_id'],'status':v['status']})
    return _serialize_worker(row)

def list_workers()->list[dict[str,Any]]:
    with get_connection() as connection:
      with connection.cursor() as cursor:
        cursor.execute('SELECT * FROM nexus.workers ORDER BY display_name,worker_id');rows=cursor.fetchall()
    return [_serialize_worker(r) for r in rows]

def _serialize_worker(r):
    return {'workerId':r['worker_id'],'workerType':r['worker_type'],'hardwareType':r['hardware_type'],'displayName':r['display_name'],'assetId':r['asset_id'],'assetMatched':r['asset_matched'],'reconciliationStatus':r['reconciliation_status'],'poolId':r['pool_id'],'poolInstanceId':r['pool_instance_id'],'nativePoolId':r['native_pool_id'],'poolHost':r['pool_host'],'poolApiPort':r['pool_api_port'],'workerName':r['worker_name'],'minerAddress':r['miner_address'],'coin':r['coin'],'status':r['status'],'currentHashrate':r['current_hashrate'],'hashrateUnit':r['hashrate_unit'],'sharesPerSecond':r['shares_per_second'],'acceptedShares':r['accepted_shares'],'rejectedShares':r['rejected_shares'],'lastShareAt':r['last_share_at'].isoformat() if r['last_share_at'] else None,'sourceSystem':r['source_system'],'sourceWorkerId':r['source_worker_id'],'classificationSource':r['classification_source'],'classificationConfidence':r['classification_confidence'],'identity':r['identity'] or {},'observedState':r['observed_state'] or {},'metadata':r['metadata'] or {},'firstSeenAt':r['first_seen_at'].isoformat(),'lastSeenAt':r['last_seen_at'].isoformat(),'updatedAt':r['updated_at'].isoformat()}
