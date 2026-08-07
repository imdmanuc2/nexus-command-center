"""Canonical CMDB object registry and relationship name resolver."""
from __future__ import annotations

from typing import Any, Callable
from urllib.parse import quote

from backend.db.repositories.asset_repository import list_assets
from backend.db.repositories.pool_repository import list_pools
from backend.db.repositories.worker_repository import list_workers
from backend.db.repositories.workload_repository import list_workloads


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _first(record: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = _text(record.get(key))
        if value:
            return value
    return ""


def _href(object_type: str, object_id: str) -> str:
    return (
        "/cmdb-object.html?type="
        + quote(object_type, safe="")
        + "&id="
        + quote(object_id, safe="")
    )


def _object(
    *,
    object_id: str,
    object_type: str,
    display_name: str,
    status: str = "unknown",
    subtitle: str = "",
    raw: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "objectId": object_id,
        "objectType": object_type,
        "displayName": display_name or object_id,
        "status": status or "unknown",
        "subtitle": subtitle,
        "href": _href(object_type, object_id),
        "raw": raw or {},
    }


def _safe_list(loader: Callable[[], list[dict[str, Any]]]) -> list[dict[str, Any]]:
    try:
        return loader()
    except Exception:
        return []


def object_registry() -> dict[str, dict[str, Any]]:
    registry: dict[str, dict[str, Any]] = {}

    for asset in _safe_list(list_assets):
        object_id = _first(asset, "assetId", "id")
        if not object_id:
            continue
        asset_type = _first(asset, "assetType", "canonicalType", "type") or "asset"
        display_name = _first(asset, "displayName", "friendlyName", "name", "ip") or object_id
        status = _first(asset, "operationalState", "status", "lifecycleStatus") or "unknown"
        subtitle = asset_type.replace("-", " ").title()
        registry[object_id] = _object(
            object_id=object_id,
            object_type="asset",
            display_name=display_name,
            status=status,
            subtitle=subtitle,
            raw=asset,
        )

    for pool in _safe_list(list_pools):
        object_id = _first(pool, "poolInstanceId", "poolId", "id")
        if not object_id:
            continue
        coin = pool.get("coin")
        if isinstance(coin, dict):
            coin = coin.get("symbol") or coin.get("name")
        display_name = _first(pool, "instanceName", "displayName", "name", "nativePoolId") or object_id
        subtitle = " ".join(part for part in (_text(coin), "Mining Pool") if part)
        registry[object_id] = _object(
            object_id=object_id,
            object_type="pool",
            display_name=display_name,
            status=_first(pool, "status") or "unknown",
            subtitle=subtitle,
            raw=pool,
        )

    # Mining engines are first-class CMDB services. The operational pool
    # identity remains stable when its implementation changes.
    for pool in _safe_list(list_pools):
        configuration = pool.get("configuration") or {}
        observed = pool.get("observedState") or {}
        implementation = _text(
            configuration.get("implementation")
            or configuration.get("software")
            or observed.get("software")
            or pool.get("instanceName")
        )
        if not implementation:
            continue
        host = _first(pool, "host")
        port = pool.get("apiPort") or (pool.get("stratumPorts") or [None])[0]
        object_id = _text(configuration.get("engineServiceId"))
        if not object_id:
            clean = "-".join(part for part in (implementation, host, str(port or "")) if part)
            object_id = "service-" + "".join(ch if ch.isalnum() else "-" for ch in clean.lower())
        registry[object_id] = _object(
            object_id=object_id,
            object_type="service",
            display_name=(pool.get("instanceName") or implementation),
            status=_first(pool, "status") or "unknown",
            subtitle="Mining Engine Service",
            raw={
                "serviceId": object_id,
                "serviceType": "mining-engine",
                "implementation": implementation,
                "host": host,
                "apiPort": pool.get("apiPort"),
                "stratumPorts": pool.get("stratumPorts") or [],
                "poolId": pool.get("poolId"),
                "configuration": configuration,
                "observedState": observed,
            },
        )

    for worker in _safe_list(list_workers):
        object_id = _first(worker, "workerId", "id")
        if not object_id:
            continue
        display_name = _first(worker, "displayName", "workerName", "sourceWorkerId") or object_id
        subtitle = " ".join(part for part in (_first(worker, "coin"), _first(worker, "workerType"), "Worker") if part)
        registry[object_id] = _object(
            object_id=object_id,
            object_type="worker",
            display_name=display_name,
            status=_first(worker, "activityState", "status") or "unknown",
            subtitle=subtitle,
            raw=worker,
        )

    for workload in _safe_list(list_workloads):
        object_id = _first(workload, "workloadId", "id")
        if not object_id:
            continue
        display_name = _first(workload, "name", "workloadName") or object_id
        registry[object_id] = _object(
            object_id=object_id,
            object_type="workload",
            display_name=display_name,
            status=_first(workload, "status") or "unknown",
            subtitle=(_first(workload, "workloadType") or "Workload").replace("-", " ").title(),
            raw=workload,
        )

    return registry


def resolve_object(object_id: str, object_type: str = "") -> dict[str, Any]:
    registry = object_registry()
    resolved = registry.get(object_id)
    if resolved:
        return resolved
    fallback_type = object_type or "object"
    return _object(
        object_id=object_id,
        object_type=fallback_type,
        display_name=object_id,
        subtitle=fallback_type.replace("-", " ").title(),
    )


def list_objects() -> dict[str, Any]:
    rows = list(object_registry().values())
    rows.sort(key=lambda row: (row["objectType"], row["displayName"].lower()))
    by_type: dict[str, int] = {}
    for row in rows:
        by_type[row["objectType"]] = by_type.get(row["objectType"], 0) + 1
    return {
        "status": "ok",
        "source": "nexus-postgresql-cmdb",
        "count": len(rows),
        "byType": by_type,
        "objects": rows,
    }


def object_detail(object_type: str, object_id: str) -> dict[str, Any]:
    resolved = resolve_object(object_id, object_type)
    if resolved["displayName"] == object_id and not resolved.get("raw"):
        return {
            "status": "not-found",
            "source": "nexus-postgresql-cmdb",
            "object": resolved,
        }

    from backend.db.repositories.relationship_repository import list_relationships

    relationships = []
    for relationship in list_relationships():
        if object_id not in {relationship.get("sourceId"), relationship.get("targetId")}:
            continue
        source = resolve_object(
            _text(relationship.get("sourceId")),
            _text(relationship.get("sourceType")),
        )
        target = resolve_object(
            _text(relationship.get("targetId")),
            _text(relationship.get("targetType")),
        )
        relationships.append({
            **relationship,
            "sourceName": source["displayName"],
            "sourceHref": source["href"],
            "sourceObject": source,
            "targetName": target["displayName"],
            "targetHref": target["href"],
            "targetObject": target,
        })

    raw = resolved.get("raw") or {}
    current_hashrate = raw.get("currentHashrate") or (raw.get("observedState") or {}).get("hashrate") or 0
    summary = {
        "identity": resolved.get("displayName"),
        "type": resolved.get("objectType"),
        "status": resolved.get("status"),
        "mission": raw.get("mission") or raw.get("purpose") or (
            "Provide mining services" if resolved.get("objectType") in {"pool", "service"}
            else "Participate in the managed Nexus environment"
        ),
        "role": raw.get("role") or raw.get("primaryRole") or "",
        "managementModel": raw.get("managementModel") or ("nexus-managed" if raw.get("managed") else "observed"),
        "lifecycleStage": raw.get("lifecycleStage") or raw.get("lifecycleStatus") or "unknown",
        "desiredOperationalState": raw.get("desiredOperationalState") or "automatic",
        "observedOperationalState": raw.get("observedOperationalState") or raw.get("activityState") or raw.get("status") or "unknown",
        "health": raw.get("health") or "unknown",
        "connectivity": raw.get("connectivity") or ("connected" if raw.get("currentSession") else "unknown"),
        "currentHashrate": current_hashrate,
        "coin": raw.get("coin"),
        "host": raw.get("host") or raw.get("ip") or raw.get("poolHost"),
        "lastObservedAt": raw.get("lastSeenAt") or raw.get("lastShareAt") or raw.get("updatedAt"),
    }

    return {
        "status": "ok",
        "source": "nexus-postgresql-cmdb",
        "object": resolved,
        "summary": summary,
        "relationships": relationships,
        "relationshipCount": len(relationships),
    }
