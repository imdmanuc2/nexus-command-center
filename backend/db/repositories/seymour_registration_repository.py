from __future__ import annotations
import hashlib, json
from typing import Any
from uuid import uuid4
from psycopg.types.json import Jsonb
from backend.db.connection import transaction
from backend.db.repositories import seymour_telemetry_repository
from backend.db.repositories import seymour_runtime_state_repository


def _hash(payload: dict[str, Any]) -> str:
    raw=json.dumps(payload,sort_keys=True,separators=(",",":")).encode()
    return hashlib.sha256(raw).hexdigest()


def _asset_values(asset: dict[str, Any], document: dict[str, Any]) -> dict[str, Any]:
    asset_type=str(asset.get("assetType") or "unknown")
    name=str(asset.get("name") or asset.get("assetId") or "Seymour Asset")
    telemetry=asset.get("telemetry") if isinstance(asset.get("telemetry"),dict) else {}
    sync=asset.get("sync") if isinstance(asset.get("sync"),dict) else {}
    return {
        "asset_id":str(asset["assetId"]),
        "asset_type":asset_type,
        "canonical_type":asset_type,
        "name":name,
        "purpose":"Blockchain Management" if asset_type=="blockchain-manager" else "Blockchain",
        "primary_role":"Seymour Blockchain Manager" if asset_type=="blockchain-manager" else "Blockchain Node",
        "coin":asset.get("coin"),
        "capabilities":Jsonb(document.get("capabilities",[]) if asset_type=="blockchain-manager" else []),
        "observed_state":Jsonb({"status":asset.get("status"),"telemetry":telemetry,"sync":sync}),
        "metadata":Jsonb({
            "source":"seymour-blockchain-manager",
            "managedBy":asset.get("managedBy") or "nexus",
            "appId":asset.get("appId"),
            "providerId":asset.get("providerId"),
            "hostname":asset.get("hostname"),
            "network":asset.get("network"),
        }),
    }


def _upsert_asset(cur, asset: dict[str, Any], document: dict[str, Any]) -> str:
    v=_asset_values(asset,document)
    cur.execute("""
      INSERT INTO nexus.assets(
        asset_id,asset_type,canonical_type,name,friendly_name,display_name,
        purpose,primary_role,coin,lifecycle_status,managed,capabilities,
        observed_state,metadata,created_automatically,updated_at,last_seen_at,retired_at
      )
      VALUES(
        %(asset_id)s,%(asset_type)s,%(canonical_type)s,%(name)s,%(name)s,%(name)s,
        %(purpose)s,%(primary_role)s,%(coin)s,'managed',TRUE,%(capabilities)s,
        %(observed_state)s,%(metadata)s,TRUE,NOW(),NOW(),NULL
      )
      ON CONFLICT(asset_id) DO UPDATE SET
        asset_type=EXCLUDED.asset_type,canonical_type=EXCLUDED.canonical_type,
        name=EXCLUDED.name,friendly_name=EXCLUDED.friendly_name,display_name=EXCLUDED.display_name,
        purpose=EXCLUDED.purpose,primary_role=EXCLUDED.primary_role,coin=EXCLUDED.coin,
        lifecycle_status='managed',managed=TRUE,capabilities=EXCLUDED.capabilities,
        observed_state=EXCLUDED.observed_state,
        metadata=nexus.assets.metadata||EXCLUDED.metadata,
        updated_at=NOW(),last_seen_at=NOW(),retired_at=NULL
      RETURNING asset_id
    """,v)
    return str(cur.fetchone()["asset_id"])


def _sync_value(sync: dict[str, Any], *names: str):
    for n in names:
        if sync.get(n) is not None: return sync.get(n)
    snap=sync.get("snapshot")
    if isinstance(snap,dict):
        for n in names:
            if snap.get(n) is not None: return snap.get(n)
    return None


def _provider_implementation(asset: dict[str, Any]) -> str:
    telemetry = asset.get("telemetry") if isinstance(asset.get("telemetry"), dict) else {}
    explicit = str(telemetry.get("implementation") or "").strip()
    if explicit:
        return explicit

    provider_id = str(asset.get("providerId") or "").strip()
    implementations = {
        "bitcoin-mainnet": "Bitcoin Core",
        "bitcoin-cash-mainnet": "Bitcoin Cash Node",
        "monero-mainnet": "Monero",
    }
    if provider_id in implementations:
        return implementations[provider_id]

    return str(asset.get("coin") or "Blockchain") + " Node"


def _operational_status(asset: dict[str, Any]) -> str:
    telemetry = asset.get("telemetry") if isinstance(asset.get("telemetry"), dict) else {}

    for value in (
        asset.get("status"),
        telemetry.get("lifecycleStatus"),
        telemetry.get("runtimeState"),
    ):
        if value is not None and str(value).strip():
            status = str(value).strip().lower()
            if status in {"running", "online", "active", "healthy", "ready"}:
                return "running"
            if status in {"stopped", "offline", "inactive"}:
                return "stopped"
            return status

    running = telemetry.get("running")
    if isinstance(running, bool):
        return "running" if running else "stopped"

    installed = telemetry.get("installed")
    if installed is False:
        return "not-installed"

    return "unknown"


def _upsert_node(cur, asset: dict[str, Any]) -> None:
    if str(asset.get("assetType"))!="blockchain-node": return
    sync=asset.get("sync") if isinstance(asset.get("sync"),dict) else {}
    tel=asset.get("telemetry") if isinstance(asset.get("telemetry"),dict) else {}
    height=_sync_value(sync,"height")
    headers=_sync_value(sync,"headers")
    peers=tel.get("peers") if tel.get("peers") is not None else _sync_value(sync,"peers")
    progress=_sync_value(sync,"progressPercent","progress_percent")
    status=_operational_status(asset)
    sync_status="synced" if progress is not None and float(progress)>=99.999 else "syncing" if progress is not None else "unknown"
    node_id="node-"+str(asset["assetId"]).removeprefix("asset-")
    cur.execute("""
      INSERT INTO nexus.blockchain_nodes(
        node_id,asset_id,coin,network,implementation,version,status,sync_status,
        block_height,header_height,peer_count,observed_state,metadata,updated_at,last_seen_at
      )
      VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NOW(),NOW())
      ON CONFLICT(asset_id,coin,network) DO UPDATE SET
        implementation=EXCLUDED.implementation,version=EXCLUDED.version,
        status=EXCLUDED.status,sync_status=EXCLUDED.sync_status,
        block_height=EXCLUDED.block_height,header_height=EXCLUDED.header_height,
        peer_count=EXCLUDED.peer_count,observed_state=EXCLUDED.observed_state,
        metadata=nexus.blockchain_nodes.metadata||EXCLUDED.metadata,
        updated_at=NOW(),last_seen_at=NOW()
    """,(node_id,str(asset["assetId"]),str(asset.get("coin") or "BCH"),
         str(asset.get("network") or "mainnet"),
         _provider_implementation(asset),
         str(tel.get("version") or ""),status,sync_status,height,headers,peers,
         Jsonb({"telemetry":tel,"sync":sync}),
         Jsonb({"source":"seymour-blockchain-manager","appId":asset.get("appId"),"providerId":asset.get("providerId")})))
    for metric,value,unit in (
        ("block_height",height,"blocks"),("header_height",headers,"blocks"),
        ("peer_count",peers,"peers"),("sync_progress",progress,"percent")
    ):
        if value is None: continue
        cur.execute("""
          INSERT INTO nexus.current_metrics(
            subject_type,subject_id,metric_name,metric_value,metric_unit,status,
            observed_at,dimensions,data
          )
          VALUES('blockchain-node',%s,%s,%s,%s,%s,NOW(),'{}'::JSONB,%s)
          ON CONFLICT(subject_type,subject_id,metric_name) DO UPDATE SET
            metric_value=EXCLUDED.metric_value,metric_unit=EXCLUDED.metric_unit,
            status=EXCLUDED.status,observed_at=EXCLUDED.observed_at,data=EXCLUDED.data
        """,(str(asset["assetId"]),metric,float(value),unit,status,
             Jsonb({"source":"seymour-blockchain-manager"})))


def _upsert_relationship(cur, rel: dict[str, Any]) -> None:
    sid=str(rel.get("sourceAssetId") or ""); tid=str(rel.get("targetAssetId") or "")
    typ=str(rel.get("relationshipType") or "")
    if not sid or not tid or not typ: return
    rid="relationship-seymour-"+hashlib.sha256(f"{sid}:{typ}:{tid}".encode()).hexdigest()[:20]
    cur.execute("""
      INSERT INTO nexus.relationships(
        relationship_id,source_type,source_id,relationship_type,target_type,target_id,
        status,confidence,source,observed,approved,metadata
      )
      VALUES(%s,'asset',%s,%s,'asset',%s,'active',100,'seymour-registration',TRUE,TRUE,%s)
      ON CONFLICT(source_type,source_id,relationship_type,target_type,target_id) DO UPDATE SET
        status='active',confidence=100,source='seymour-registration',
        observed=TRUE,approved=TRUE,metadata=EXCLUDED.metadata,last_seen_at=NOW(),updated_at=NOW()
    """,(rid,sid,typ,tid,Jsonb({"source":"seymour-blockchain-manager"})))


def latest():
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM nexus.seymour_registrations ORDER BY received_at DESC LIMIT 1")
            row=cur.fetchone()
            return dict(row) if row else None


def ingest(payload: dict[str, Any], idempotency_key: str) -> dict[str, Any]:
    registration_id=str(payload.get("registrationId") or "")
    document=payload.get("document")
    if not registration_id: raise ValueError("registrationId is required.")
    if not isinstance(document,dict): raise ValueError("document is required.")
    assets=document.get("assets")
    if not isinstance(assets,list) or not assets: raise ValueError("document.assets must be a non-empty list.")
    digest=_hash(payload)
    manager_id=None; node_ids=[]
    with transaction() as conn:
        with conn.cursor() as cur:
            cur.execute("""
              SELECT registration_id,payload_hash,result
              FROM nexus.seymour_registrations
              WHERE idempotency_key=%s
              FOR UPDATE
            """,(idempotency_key,))
            existing=cur.fetchone()
            if existing:
                if str(existing["payload_hash"])!=digest:
                    raise ValueError("Idempotency key or registrationId reused with different payload.")
                result=existing["result"] or {}
                seymour_telemetry_repository.project_document(cur, document)
                seymour_runtime_state_repository.project_document(cur, document)
                cur.execute(
                    "UPDATE nexus.seymour_registrations SET last_seen_at=NOW() WHERE registration_id=%s",
                    (registration_id,),
                )
                return {**result,"duplicate":True,"registrationId":registration_id}
            for asset in assets:
                if not isinstance(asset,dict) or not asset.get("assetId"): continue
                aid=_upsert_asset(cur,asset,document)
                if asset.get("assetType")=="blockchain-manager": manager_id=aid
                if asset.get("assetType")=="blockchain-node":
                    node_ids.append(aid); _upsert_node(cur,asset)
            for rel in document.get("relationships",[]):
                if isinstance(rel,dict): _upsert_relationship(cur,rel)
            metrics_written = seymour_telemetry_repository.project_document(cur, document)
            seymour_runtime_state_repository.project_document(cur, document)

            result={
                "status":"accepted","registrationId":registration_id,
                "managerAssetId":manager_id,"nodeAssetIds":node_ids,
                "assetCount":len([x for x in assets if isinstance(x,dict) and x.get("assetId")]),
                "relationshipCount":len([x for x in document.get("relationships",[]) if isinstance(x,dict)]),
                "metricsWritten":metrics_written,
                "duplicate":False,
            }
            cur.execute("""
              INSERT INTO nexus.seymour_registrations(
                registration_id,idempotency_key,source,manager_asset_id,node_asset_ids,
                payload_hash,status,raw_payload,result,processed_at
              )
              VALUES(%s,%s,%s,%s,%s,%s,'accepted',%s,%s,NOW())
              ON CONFLICT (registration_id)
              DO UPDATE SET
                idempotency_key = EXCLUDED.idempotency_key,
                source = EXCLUDED.source,
                manager_asset_id = EXCLUDED.manager_asset_id,
                node_asset_ids = EXCLUDED.node_asset_ids,
                payload_hash = EXCLUDED.payload_hash,
                status = 'accepted',
                raw_payload = EXCLUDED.raw_payload,
                result = EXCLUDED.result,
                last_seen_at = NOW(),
                processed_at = NOW()
            """,(registration_id,idempotency_key,str(payload.get("source") or "seymour-blockchain-manager"),
                 manager_id,Jsonb(node_ids),digest,Jsonb(payload),Jsonb(result)))
            audit_asset=node_ids[0] if node_ids else manager_id
            cur.execute("""
              INSERT INTO nexus.audit_events(
                event_id,occurred_at,category,action,asset_id,asset_type,asset_name,
                actor_type,actor_id,source,reason,correlation_id,confidence,changes,metadata
              )
              VALUES(%s,NOW(),'cmdb','seymour-registration-ingested',%s,'blockchain-node',
                'Seymour Blockchain Registration','system','seymour-blockchain-manager',
                'seymour-registration','Authenticated Seymour registration reconciled into CMDB.',
                %s,100,'[]'::JSONB,%s)
            """,(f"audit-{uuid4().hex}",audit_asset,registration_id,
                 Jsonb({"registrationId":registration_id,"managerAssetId":manager_id,"nodeAssetIds":node_ids})))
    return result
