"""PostgreSQL repository for MiningCore instances."""
from typing import Any
from psycopg.types.json import Jsonb
from backend.db.connection import get_connection, transaction

def upsert_miningcore_instance(instance: dict[str, Any]) -> dict[str, Any]:
    instance_id = str(instance.get("instance_id") or "").strip()
    endpoint = str(instance.get("endpoint") or instance.get("api_base_url") or "").strip()
    if not instance_id:
        raise ValueError("MiningCore instance_id is required.")
    if not endpoint:
        raise ValueError("MiningCore endpoint is required.")

    connected = bool(instance.get("connected"))
    status = str(instance.get("status") or ("online" if connected else "offline"))
    health = str(instance.get("health") or ("healthy" if connected else "unreachable"))
    version = str(instance.get("version") or instance.get("software_version") or "")

    p = {
        "instance_id": instance_id,
        "asset_id": instance.get("asset_id"),
        "site_id": instance.get("site_id"),
        "name": str(instance.get("name") or "MiningCore"),
        "status": status,
        "environment": str(instance.get("environment") or "production"),
        "api_base_url": endpoint,
        "console_url": str(instance.get("console_url") or ""),
        "software_version": version,
        "health_score": instance.get("health_score"),
        "api_online": bool(instance.get("api_online", connected)),
        "api_latency_ms": instance.get("api_latency_ms"),
        "console_online": bool(instance.get("console_online", False)),
        "process_uptime_sec": instance.get("process_uptime_sec"),
        "restart_count": int(instance.get("restart_count") or 0),
        "license_status": str(instance.get("license_status") or "unknown"),
        "developer_fee_status": str(instance.get("developer_fee_status") or "unknown"),
        "observed_state": Jsonb(instance.get("observed_state") or {}),
        "metadata": Jsonb(instance.get("metadata") or {}),
        "endpoint": endpoint,
        "host": str(instance.get("host") or ""),
        "port": instance.get("port"),
        "connected": connected,
        "health": health,
        "version": version,
        "pool_count": int(instance.get("pool_count") or 0),
        "raw_payload": Jsonb(instance.get("raw_payload") or {}),
    }

    with transaction() as connection:
        with connection.cursor() as cur:
            cur.execute("""
                INSERT INTO nexus.miningcore_instances (
                    instance_id, asset_id, site_id, name, status, environment,
                    api_base_url, console_url, software_version, health_score,
                    api_online, api_latency_ms, console_online, process_uptime_sec,
                    restart_count, license_status, developer_fee_status,
                    observed_state, metadata, endpoint, host, port, connected,
                    health, version, pool_count, created_at, first_seen_at,
                    last_seen_at, last_changed_at, raw_payload, updated_at
                ) VALUES (
                    %(instance_id)s, %(asset_id)s, %(site_id)s, %(name)s,
                    %(status)s, %(environment)s, %(api_base_url)s,
                    %(console_url)s, %(software_version)s, %(health_score)s,
                    %(api_online)s, %(api_latency_ms)s, %(console_online)s,
                    %(process_uptime_sec)s, %(restart_count)s, %(license_status)s,
                    %(developer_fee_status)s, %(observed_state)s, %(metadata)s,
                    %(endpoint)s, %(host)s, %(port)s, %(connected)s, %(health)s,
                    %(version)s, %(pool_count)s, NOW(), NOW(), NOW(), NOW(),
                    %(raw_payload)s, NOW()
                )
                ON CONFLICT (instance_id) DO UPDATE SET
                    asset_id = COALESCE(EXCLUDED.asset_id, nexus.miningcore_instances.asset_id),
                    site_id = COALESCE(EXCLUDED.site_id, nexus.miningcore_instances.site_id),
                    name = EXCLUDED.name,
                    status = EXCLUDED.status,
                    environment = EXCLUDED.environment,
                    api_base_url = EXCLUDED.api_base_url,
                    console_url = EXCLUDED.console_url,
                    software_version = EXCLUDED.software_version,
                    health_score = EXCLUDED.health_score,
                    api_online = EXCLUDED.api_online,
                    api_latency_ms = EXCLUDED.api_latency_ms,
                    console_online = EXCLUDED.console_online,
                    process_uptime_sec = EXCLUDED.process_uptime_sec,
                    restart_count = EXCLUDED.restart_count,
                    license_status = EXCLUDED.license_status,
                    developer_fee_status = EXCLUDED.developer_fee_status,
                    observed_state = EXCLUDED.observed_state,
                    metadata = EXCLUDED.metadata,
                    endpoint = EXCLUDED.endpoint,
                    host = EXCLUDED.host,
                    port = EXCLUDED.port,
                    connected = EXCLUDED.connected,
                    health = EXCLUDED.health,
                    version = EXCLUDED.version,
                    pool_count = EXCLUDED.pool_count,
                    last_seen_at = NOW(),
                    last_changed_at = CASE WHEN (
                        nexus.miningcore_instances.connected,
                        nexus.miningcore_instances.status,
                        nexus.miningcore_instances.health,
                        nexus.miningcore_instances.version,
                        nexus.miningcore_instances.pool_count,
                        nexus.miningcore_instances.endpoint
                    ) IS DISTINCT FROM (
                        EXCLUDED.connected, EXCLUDED.status, EXCLUDED.health,
                        EXCLUDED.version, EXCLUDED.pool_count, EXCLUDED.endpoint
                    ) THEN NOW() ELSE nexus.miningcore_instances.last_changed_at END,
                    raw_payload = EXCLUDED.raw_payload,
                    updated_at = NOW()
                RETURNING *
            """, p)
            row = cur.fetchone()
    return _serialize(row)

def list_miningcore_instances() -> list[dict[str, Any]]:
    with get_connection() as connection:
        with connection.cursor() as cur:
            cur.execute("SELECT * FROM nexus.miningcore_instances ORDER BY name, instance_id")
            rows = cur.fetchall()
    return [_serialize(r) for r in rows]

def mark_stale_miningcore_instances(stale_seconds: int = 300) -> int:
    with transaction() as connection:
        with connection.cursor() as cur:
            cur.execute("""
                UPDATE nexus.miningcore_instances
                SET connected=FALSE, api_online=FALSE, status='offline',
                    health='unreachable', updated_at=NOW()
                WHERE last_seen_at < NOW() - (%s * INTERVAL '1 second')
                  AND status <> 'offline'
            """, (stale_seconds,))
            return cur.rowcount

def _serialize(row: dict[str, Any]) -> dict[str, Any]:
    def iso(name):
        value = row.get(name)
        return value.isoformat() if value else None
    return {
        "instanceId": row["instance_id"],
        "assetId": row.get("asset_id"),
        "siteId": row.get("site_id"),
        "name": row["name"],
        "status": row["status"],
        "environment": row["environment"],
        "apiBaseUrl": row["api_base_url"],
        "consoleUrl": row["console_url"],
        "softwareVersion": row["software_version"],
        "healthScore": float(row["health_score"]) if row.get("health_score") is not None else None,
        "apiOnline": row["api_online"],
        "apiLatencyMs": float(row["api_latency_ms"]) if row.get("api_latency_ms") is not None else None,
        "consoleOnline": row["console_online"],
        "processUptimeSec": row.get("process_uptime_sec"),
        "restartCount": row["restart_count"],
        "licenseStatus": row["license_status"],
        "developerFeeStatus": row["developer_fee_status"],
        "observedState": row["observed_state"] or {},
        "metadata": row["metadata"] or {},
        "endpoint": row["endpoint"],
        "host": row["host"],
        "port": row["port"],
        "connected": row["connected"],
        "health": row["health"],
        "version": row["version"],
        "poolCount": row["pool_count"],
        "createdAt": iso("created_at"),
        "firstSeenAt": iso("first_seen_at"),
        "lastSeenAt": iso("last_seen_at"),
        "lastChangedAt": iso("last_changed_at"),
        "updatedAt": iso("updated_at"),
        "raw": row["raw_payload"] or {},
    }
