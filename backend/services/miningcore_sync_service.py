"""Synchronize live MiningCore connector state into PostgreSQL."""
from typing import Any
from backend.db.repositories.miningcore_repository import (
    mark_stale_miningcore_instances, upsert_miningcore_instance
)
from backend.services.resource_sync_common import fetch_json, parse_endpoint, stable_id

def synchronize_miningcore_instances(stale_seconds: int = 300) -> dict[str, Any]:
    payload = fetch_json("/api/connectors/status")
    connector = ((payload.get("connectors") or {}).get("miningcore") or {})
    instances = connector.get("instances") or []
    written = []

    for raw in instances:
        endpoint = str(raw.get("endpoint") or "")
        parsed_host, parsed_port = parse_endpoint(endpoint)
        host = str(raw.get("host") or parsed_host)
        port = raw.get("port") or parsed_port
        name = str(raw.get("name") or host or endpoint or "MiningCore")
        connected = bool(raw.get("connected"))
        status = "online" if connected else "offline"
        health = "healthy" if connected else "unreachable"
        version = str(raw.get("version") or "")
        instance_id = str(
            raw.get("instanceId") or raw.get("id")
            or stable_id("miningcore", endpoint, host, name)
        )

        written.append(upsert_miningcore_instance({
            "instance_id": instance_id,
            "asset_id": raw.get("assetId"),
            "site_id": raw.get("siteId"),
            "name": name,
            "status": status,
            "environment": str(raw.get("environment") or "production"),
            "api_base_url": endpoint,
            "console_url": str(raw.get("consoleUrl") or ""),
            "software_version": version,
            "health_score": 100.0 if connected else 0.0,
            "api_online": connected,
            "api_latency_ms": raw.get("apiLatencyMs"),
            "console_online": bool(raw.get("consoleOnline", False)),
            "process_uptime_sec": raw.get("processUptimeSec"),
            "restart_count": int(raw.get("restartCount") or 0),
            "license_status": str(raw.get("licenseStatus") or "unknown"),
            "developer_fee_status": str(raw.get("developerFeeStatus") or "unknown"),
            "observed_state": {
                "connected": connected,
                "poolCount": int(raw.get("poolCount") or 0),
                "endpoint": endpoint,
                "host": host,
                "port": port,
            },
            "metadata": {
                "connectorName": connector.get("name"),
                "connectorConnected": connector.get("connected"),
                "connectorInstanceCount": connector.get("instanceCount"),
            },
            "endpoint": endpoint,
            "host": host,
            "port": port,
            "connected": connected,
            "health": health,
            "version": version,
            "pool_count": int(raw.get("poolCount") or 0),
            "raw_payload": raw,
        }))

    return {
        "status": "ok",
        "source": "miningcore-resource-sync",
        "observed": len(instances),
        "written": len(written),
        "markedOffline": mark_stale_miningcore_instances(stale_seconds),
        "instances": written,
    }
