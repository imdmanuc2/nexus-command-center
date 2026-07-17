"""PostgreSQL-backed observation compatibility layer."""
from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from backend.db.repositories import observation_repository

def now_iso(): return datetime.now(timezone.utc).isoformat()
def _s(v): return "" if v is None else str(v).strip()
def _l(v):
    if v is None: return []
    if isinstance(v, list): return v
    if isinstance(v, (tuple,set)): return list(v)
    return [v]

def normalize_observation(payload, source="unknown", observer_id="nexus", correlation_id=None):
    if not isinstance(payload, dict): raise ValueError("Observation payload must be an object.")
    ident = dict(payload.get("identity") or {})
    return {
      "observationId": payload.get("observationId") or f"obs-{uuid4().hex}",
      "observedAt": payload.get("observedAt") or payload.get("lastSeen") or now_iso(),
      "receivedAt": now_iso(), "source": payload.get("source") or source,
      "observerId": payload.get("observerId") or observer_id,
      "correlationId": payload.get("correlationId") or correlation_id or f"corr-{uuid4().hex}",
      "status": payload.get("status") or "pending", "decision": payload.get("decision") or "",
      "matchedAssetId": payload.get("matchedAssetId") or "", "confidence": payload.get("confidence"),
      "identity": {
        "ip": _s(ident.get("ip") or payload.get("ip")),
        "macAddress": _s(ident.get("macAddress") or payload.get("macAddress") or payload.get("mac")).lower(),
        "serialNumber": _s(ident.get("serialNumber") or payload.get("serialNumber") or payload.get("serial")),
        "hostname": _s(ident.get("hostname") or payload.get("hostname")).lower(),
        "machineUuid": _s(ident.get("machineUuid") or payload.get("machineUuid") or payload.get("systemUuid") or payload.get("vmUuid")).lower(),
        "sshHostKey": _s(ident.get("sshHostKey") or payload.get("sshHostKey")),
        "workerId": _s(ident.get("workerId") or payload.get("workerId")),
        "poolId": _s(ident.get("poolId") or payload.get("poolId"))
      },
      "classification": {
        "assetType": payload.get("assetType") or payload.get("canonicalType") or payload.get("type") or "unknown",
        "primaryRole": payload.get("primaryRole") or "", "purpose": payload.get("purpose") or ""
      },
      "network": {"ip": _s(payload.get("ip")),
                  "openPorts": _l(payload.get("openPorts") or payload.get("ports")),
                  "services": _l(payload.get("services"))},
      "compute": {"computeProfile": payload.get("computeProfile") if isinstance(payload.get("computeProfile"), dict) else {},
                  "components": _l(payload.get("components")), "capabilities": _l(payload.get("capabilities")),
                  "workloads": _l(payload.get("workloads"))},
      "raw": payload
    }

def append_observation(payload, source="unknown", observer_id="nexus", correlation_id=None):
    return observation_repository.append_observation(
      normalize_observation(payload, source, observer_id, correlation_id))

def read_observations(**kwargs): return observation_repository.read_observations(**kwargs)
