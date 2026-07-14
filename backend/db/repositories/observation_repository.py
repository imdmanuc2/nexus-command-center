"""PostgreSQL repository for Nexus observations."""
from __future__ import annotations
from typing import Any
from psycopg.types.json import Jsonb
from backend.db.connection import get_connection

def append_observation(obs: dict[str, Any]) -> dict[str, Any]:
    v = {
      "id": obs["observationId"], "observed": obs["observedAt"], "received": obs["receivedAt"],
      "source": obs.get("source") or "unknown", "observer": obs.get("observerId") or "nexus",
      "corr": obs["correlationId"], "status": obs.get("status") or "pending",
      "decision": obs.get("decision") or "", "asset": obs.get("matchedAssetId") or None,
      "confidence": obs.get("confidence"), "identity": Jsonb(obs.get("identity") or {}),
      "classification": Jsonb(obs.get("classification") or {}), "network": Jsonb(obs.get("network") or {}),
      "compute": Jsonb(obs.get("compute") or {}), "raw": Jsonb(obs.get("raw") or {})
    }
    with get_connection() as c:
        with c.cursor() as cur:
            cur.execute("""
              INSERT INTO nexus.observations (
                observation_id, observed_at, received_at, source, observer_id,
                correlation_id, status, decision, matched_asset_id, confidence,
                identity, classification, network, compute, raw_payload
              ) VALUES (
                %(id)s, %(observed)s::timestamptz, %(received)s::timestamptz,
                %(source)s, %(observer)s, %(corr)s, %(status)s, %(decision)s,
                %(asset)s, %(confidence)s, %(identity)s, %(classification)s,
                %(network)s, %(compute)s, %(raw)s
              ) ON CONFLICT (observation_id) DO NOTHING
            """, v)
        c.commit()
    return obs

def update_observation(observation_id, status, decision, matched_asset_id=None, confidence=None):
    with get_connection() as c:
        with c.cursor() as cur:
            cur.execute("""UPDATE nexus.observations SET status=%s, decision=%s,
                matched_asset_id=%s, confidence=%s WHERE observation_id=%s""",
                (status, decision, matched_asset_id, confidence, observation_id))
        c.commit()

def read_observations(status=None, matched_asset_id=None, correlation_id=None, limit=200):
    clauses, vals = [], []
    for col, val in [("status", status), ("matched_asset_id", matched_asset_id),
                     ("correlation_id", correlation_id)]:
        if val:
            clauses.append(f"{col}=%s"); vals.append(val)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    vals.append(max(1, min(int(limit), 5000)))
    with get_connection() as c:
        with c.cursor() as cur:
            cur.execute(f"SELECT * FROM nexus.observations{where} ORDER BY received_at DESC LIMIT %s", vals)
            rows = cur.fetchall()
    return [{
      "observationId": r["observation_id"], "observedAt": r["observed_at"].isoformat(),
      "receivedAt": r["received_at"].isoformat(), "source": r["source"],
      "observerId": r["observer_id"], "correlationId": r["correlation_id"],
      "status": r["status"], "decision": r["decision"],
      "matchedAssetId": r["matched_asset_id"] or "",
      "confidence": float(r["confidence"]) if r["confidence"] is not None else None,
      "identity": r["identity"] or {}, "classification": r["classification"] or {},
      "network": r["network"] or {}, "compute": r["compute"] or {}, "raw": r["raw_payload"] or {}
    } for r in rows]
