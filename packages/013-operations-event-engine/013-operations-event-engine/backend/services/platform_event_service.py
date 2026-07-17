from __future__ import annotations

import hashlib
import json
from typing import Any

from backend.db.repositories.blockchain_repository import list_blockchain_nodes
from backend.db.repositories.miningcore_repository import list_miningcore_instances
from backend.db.repositories.pool_repository import list_pools
from backend.db.repositories.worker_repository import list_workers
from backend.db.repositories.platform_event_repository import (
    append_event,
    get_snapshot,
    upsert_snapshot,
)


def _hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _resources():
    for worker in list_workers():
        entity_id = str(worker.get("workerId") or "")
        if entity_id:
            yield "worker", entity_id, {
                "status": worker.get("status"),
                "assetId": worker.get("assetId"),
                "poolInstanceId": worker.get("poolInstanceId"),
                "currentHashrate": worker.get("currentHashrate"),
            }

    for pool in list_pools():
        entity_id = str(pool.get("poolId") or "")
        if entity_id:
            yield "pool", entity_id, {
                "status": pool.get("status"),
                "currentHashrate": pool.get("currentHashrate"),
                "workerCount": pool.get("workerCount"),
            }

    for node in list_blockchain_nodes():
        entity_id = str(node.get("nodeId") or "")
        if entity_id:
            yield "blockchain-node", entity_id, {
                "status": node.get("status"),
                "rpcConnected": node.get("rpcConnected"),
                "version": node.get("version"),
                "blockHeight": node.get("blockHeight"),
                "peers": node.get("peers"),
            }

    for instance in list_miningcore_instances():
        entity_id = str(instance.get("instanceId") or "")
        if entity_id:
            yield "miningcore-instance", entity_id, {
                "status": instance.get("status"),
                "connected": instance.get("connected"),
                "health": instance.get("health"),
                "version": instance.get("version"),
                "poolCount": instance.get("poolCount"),
                "endpoint": instance.get("endpoint"),
            }


def _event_type(previous: dict[str, Any], current: dict[str, Any]) -> str:
    if previous.get("status") != current.get("status"):
        status = str(current.get("status") or "").lower()
        if status in {"offline", "down", "error", "failed"}:
            return "resource.offline"
        if status in {"online", "healthy", "running"}:
            return "resource.online"
        return "resource.status_changed"
    if previous.get("endpoint") != current.get("endpoint"):
        return "resource.endpoint_changed"
    if previous.get("version") != current.get("version"):
        return "resource.version_changed"
    if previous.get("poolInstanceId") != current.get("poolInstanceId"):
        return "worker.pool_changed"
    return "resource.state_changed"


def evaluate_platform_state() -> dict[str, Any]:
    evaluated = 0
    emitted = 0

    for entity_type, entity_id, current in _resources():
        evaluated += 1
        state_hash = _hash(current)
        previous = get_snapshot(entity_type, entity_id)

        if previous is None:
            append_event(
                event_type="resource.discovered",
                severity="info",
                entity_type=entity_type,
                entity_id=entity_id,
                title=f"{entity_type} discovered",
                message="Resource entered the Nexus Platform state model.",
                current_state=current,
            )
            emitted += 1
            changed = True
        else:
            changed = previous["stateHash"] != state_hash
            if changed:
                event_type = _event_type(
                    previous["statePayload"],
                    current,
                )
                severity = (
                    "critical"
                    if event_type == "resource.offline"
                    else "info"
                )
                append_event(
                    event_type=event_type,
                    severity=severity,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    title=event_type.replace(".", " ").title(),
                    message="Persisted resource state changed.",
                    previous_state=previous["statePayload"],
                    current_state=current,
                )
                emitted += 1

        upsert_snapshot(
            entity_type=entity_type,
            entity_id=entity_id,
            state_hash=state_hash,
            state_payload=current,
            changed=changed,
        )

    return {
        "status": "ok",
        "source": "nexus-platform-event-engine",
        "evaluatedEntities": evaluated,
        "emittedEvents": emitted,
    }
