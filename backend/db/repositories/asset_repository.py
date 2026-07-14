"""PostgreSQL repository for Nexus CMDB assets."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable
from psycopg.types.json import Jsonb

from backend.db.connection import get_connection, transaction

CONTROL_FIELDS = {
    "_actorType", "_actorId", "_source", "_reason",
    "_correlationId", "_confidence",
}

def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()

def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}

def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []

def _iso(value: Any) -> str | None:
    if value is None:
        return None
    return value.isoformat() if isinstance(value, datetime) else str(value)

def _asset_id(asset: dict[str, Any]) -> str:
    value = _text(asset.get("id") or asset.get("assetId"))
    if not value:
        raise ValueError("Asset requires id or assetId.")
    return value

def _metadata(asset: dict[str, Any]) -> dict[str, Any]:
    existing = dict(_dict(asset.get("metadata")))
    existing["legacy"] = {
        "ip": _text(asset.get("ip")),
        "macAddress": _text(asset.get("macAddress")),
        "hostname": _text(asset.get("hostname")),
        "machineUuid": _text(
            asset.get("machineUuid")
            or asset.get("systemUuid")
            or asset.get("vmUuid")
        ),
        "sshHostKey": _text(asset.get("sshHostKey")),
        "workerId": _text(asset.get("workerId")),
        "poolId": _text(asset.get("poolId")),
        "poolHost": _text(asset.get("poolHost")),
        "poolGroup": _text(asset.get("poolGroup")),
        "openPorts": _list(asset.get("openPorts")),
        "services": _list(asset.get("services")),
        "components": _list(asset.get("components")),
        "workloads": _list(asset.get("workloads")),
        "tags": _list(asset.get("tags")),
    }
    return existing

def _upsert_row(asset: dict[str, Any], connection) -> None:
    asset_id = _asset_id(asset)
    asset_type = _text(
        asset.get("assetType")
        or asset.get("canonicalType")
        or asset.get("type")
        or "unknown"
    )
    name = _text(
        asset.get("name")
        or asset.get("friendlyName")
        or asset.get("displayName")
        or asset.get("ip")
        or asset_id
    )
    values = {
        "asset_id": asset_id,
        "asset_type": asset_type,
        "canonical_type": _text(asset.get("canonicalType") or asset_type),
        "name": name,
        "friendly_name": _text(asset.get("friendlyName") or name),
        "display_name": _text(asset.get("displayName") or asset.get("friendlyName") or name),
        "purpose": _text(asset.get("purpose")),
        "primary_role": _text(asset.get("primaryRole")),
        "coin": asset.get("coin") or None,
        "lifecycle_status": _text(asset.get("lifecycleStatus") or "managed"),
        "managed": bool(asset.get("managed", True)),
        "favorite": bool(asset.get("favorite", False)),
        "criticality": _text(asset.get("criticality") or "normal"),
        "owner": _text(asset.get("owner")),
        "business_service": _text(asset.get("businessService")),
        "location": _text(asset.get("location")),
        "rack": _text(asset.get("rack")),
        "position": _text(asset.get("position")),
        "manufacturer": _text(asset.get("manufacturer")),
        "model": _text(asset.get("model")),
        "serial_number": _text(asset.get("serialNumber")),
        "operating_system": _text(asset.get("operatingSystem")),
        "architecture": _text(asset.get("architecture")),
        "hypervisor": _text(asset.get("hypervisor")),
        "container_runtime": _text(asset.get("containerRuntime")),
        "notes": _text(asset.get("notes")),
        "compute_profile": Jsonb(_dict(asset.get("computeProfile"))),
        "capabilities": Jsonb(_list(asset.get("capabilities"))),
        "allocation": Jsonb(_dict(asset.get("allocation"))),
        "desired_state": Jsonb(_dict(asset.get("desiredState"))),
        "observed_state": Jsonb(_dict(asset.get("observedState"))),
        "metadata": Jsonb(_metadata(asset)),
        "created_automatically": bool(asset.get("createdAutomatically", False)),
        "created_at": asset.get("createdAt"),
        "updated_at": asset.get("updatedAt"),
        "last_seen_at": asset.get("lastSeenAt"),
        "retired_at": asset.get("retiredAt"),
        "site_id": asset.get("siteId") or None,
    }
    with connection.cursor() as cursor:
        cursor.execute("""
            INSERT INTO nexus.assets (
                asset_id, asset_type, canonical_type, name, friendly_name,
                display_name, purpose, primary_role, coin, lifecycle_status,
                managed, favorite, criticality, owner, business_service,
                location, rack, position, manufacturer, model, serial_number,
                operating_system, architecture, hypervisor, container_runtime,
                notes, compute_profile, capabilities, allocation, desired_state,
                observed_state, metadata, created_automatically, created_at,
                updated_at, last_seen_at, retired_at, site_id
            ) VALUES (
                %(asset_id)s, %(asset_type)s, %(canonical_type)s, %(name)s,
                %(friendly_name)s, %(display_name)s, %(purpose)s,
                %(primary_role)s, %(coin)s, %(lifecycle_status)s, %(managed)s,
                %(favorite)s, %(criticality)s, %(owner)s, %(business_service)s,
                %(location)s, %(rack)s, %(position)s, %(manufacturer)s, %(model)s,
                %(serial_number)s, %(operating_system)s, %(architecture)s,
                %(hypervisor)s, %(container_runtime)s, %(notes)s,
                %(compute_profile)s, %(capabilities)s, %(allocation)s,
                %(desired_state)s, %(observed_state)s, %(metadata)s,
                %(created_automatically)s,
                COALESCE(%(created_at)s::TIMESTAMPTZ, NOW()),
                COALESCE(%(updated_at)s::TIMESTAMPTZ, NOW()),
                %(last_seen_at)s::TIMESTAMPTZ,
                %(retired_at)s::TIMESTAMPTZ,
                %(site_id)s
            )
            ON CONFLICT (asset_id) DO UPDATE SET
                asset_type = EXCLUDED.asset_type,
                canonical_type = EXCLUDED.canonical_type,
                name = EXCLUDED.name,
                friendly_name = EXCLUDED.friendly_name,
                display_name = EXCLUDED.display_name,
                purpose = EXCLUDED.purpose,
                primary_role = EXCLUDED.primary_role,
                coin = EXCLUDED.coin,
                lifecycle_status = EXCLUDED.lifecycle_status,
                managed = EXCLUDED.managed,
                favorite = EXCLUDED.favorite,
                criticality = EXCLUDED.criticality,
                owner = EXCLUDED.owner,
                business_service = EXCLUDED.business_service,
                location = EXCLUDED.location,
                rack = EXCLUDED.rack,
                position = EXCLUDED.position,
                manufacturer = EXCLUDED.manufacturer,
                model = EXCLUDED.model,
                serial_number = EXCLUDED.serial_number,
                operating_system = EXCLUDED.operating_system,
                architecture = EXCLUDED.architecture,
                hypervisor = EXCLUDED.hypervisor,
                container_runtime = EXCLUDED.container_runtime,
                notes = EXCLUDED.notes,
                compute_profile = EXCLUDED.compute_profile,
                capabilities = EXCLUDED.capabilities,
                allocation = EXCLUDED.allocation,
                desired_state = EXCLUDED.desired_state,
                observed_state = EXCLUDED.observed_state,
                metadata = EXCLUDED.metadata,
                created_automatically = EXCLUDED.created_automatically,
                updated_at = EXCLUDED.updated_at,
                last_seen_at = EXCLUDED.last_seen_at,
                retired_at = EXCLUDED.retired_at,
                site_id = EXCLUDED.site_id
        """, values)

def _upsert_identities(asset: dict[str, Any], connection) -> None:
    identities = [
        ("mac-address", asset.get("macAddress")),
        ("serial-number", asset.get("serialNumber")),
        ("hostname", asset.get("hostname")),
        ("machine-uuid", asset.get("machineUuid") or asset.get("systemUuid") or asset.get("vmUuid")),
        ("ssh-host-key", asset.get("sshHostKey")),
        ("worker-id", asset.get("workerId")),
    ]
    with connection.cursor() as cursor:
        for identity_type, raw in identities:
            value = _text(raw)
            if not value:
                continue
            cursor.execute("""
                INSERT INTO nexus.asset_identities (
                    asset_id, identity_type, identity_value, normalized_value,
                    confidence, source, is_primary, is_active, last_seen_at
                )
                VALUES (%s, %s, %s, %s, 100, 'json-import', TRUE, TRUE, NOW())
                ON CONFLICT (identity_type, normalized_value)
                DO UPDATE SET
                    asset_id = EXCLUDED.asset_id,
                    identity_value = EXCLUDED.identity_value,
                    is_active = TRUE,
                    last_seen_at = NOW()
            """, (_asset_id(asset), identity_type, value, value.lower()))

def _upsert_address(asset: dict[str, Any], connection) -> None:
    address = _text(asset.get("ip"))
    if not address:
        return
    asset_id = _asset_id(asset)
    address_type = "ipv6" if ":" in address else "ipv4"
    with connection.cursor() as cursor:
        cursor.execute("""
            UPDATE nexus.asset_network_addresses
            SET is_primary = FALSE
            WHERE asset_id = %s AND address <> %s
        """, (asset_id, address))
        cursor.execute("""
            INSERT INTO nexus.asset_network_addresses (
                asset_id, address_type, address, is_primary, is_active,
                first_seen_at, last_seen_at, metadata
            )
            VALUES (%s, %s, %s, TRUE, TRUE, NOW(), NOW(),
                    '{"source":"json-import"}'::JSONB)
            ON CONFLICT (asset_id, address)
            DO UPDATE SET
                is_primary = TRUE,
                is_active = TRUE,
                retired_at = NULL,
                last_seen_at = NOW()
        """, (asset_id, address_type, address))

def _replace_tags(asset: dict[str, Any], connection) -> None:
    tags = sorted({_text(tag) for tag in _list(asset.get("tags")) if _text(tag)})
    asset_id = _asset_id(asset)
    with connection.cursor() as cursor:
        cursor.execute("DELETE FROM nexus.asset_tags WHERE asset_id = %s", (asset_id,))
        for tag in tags:
            cursor.execute("""
                INSERT INTO nexus.tags(name)
                VALUES (%s)
                ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name
                RETURNING tag_id
            """, (tag,))
            tag_id = cursor.fetchone()["tag_id"]
            cursor.execute("""
                INSERT INTO nexus.asset_tags(asset_id, tag_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
            """, (asset_id, tag_id))

def upsert_asset(asset: dict[str, Any]) -> dict[str, Any]:
    with transaction() as connection:
        _upsert_row(asset, connection)
        _upsert_identities(asset, connection)
        _upsert_address(asset, connection)
        _replace_tags(asset, connection)
    result = get_asset(_asset_id(asset))
    if result is None:
        raise RuntimeError("Asset upsert completed but record could not be read.")
    return result

def bulk_upsert_assets(assets: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [upsert_asset(asset) for asset in assets]

def _select_sql(where: str = "") -> str:
    return f"""
        SELECT
            a.*,
            addr.address AS primary_ip,
            COALESCE(tags.tags, '[]'::JSONB) AS tags
        FROM nexus.assets a
        LEFT JOIN LATERAL (
            SELECT address
            FROM nexus.asset_network_addresses n
            WHERE n.asset_id = a.asset_id AND n.is_active = TRUE
            ORDER BY n.is_primary DESC, n.last_seen_at DESC
            LIMIT 1
        ) addr ON TRUE
        LEFT JOIN LATERAL (
            SELECT JSONB_AGG(t.name ORDER BY t.name) AS tags
            FROM nexus.asset_tags at
            JOIN nexus.tags t ON t.tag_id = at.tag_id
            WHERE at.asset_id = a.asset_id
        ) tags ON TRUE
        {where}
    """

def _row_to_asset(row: dict[str, Any]) -> dict[str, Any]:
    legacy = _dict(_dict(row.get("metadata")).get("legacy"))
    return {
        "id": row.get("asset_id"),
        "ip": row.get("primary_ip") or legacy.get("ip") or "",
        "name": row.get("name") or "",
        "friendlyName": row.get("friendly_name") or "",
        "displayName": row.get("display_name") or "",
        "type": row.get("asset_type") or "unknown",
        "assetType": row.get("asset_type") or "unknown",
        "canonicalType": row.get("canonical_type") or "unknown",
        "purpose": row.get("purpose") or "",
        "primaryRole": row.get("primary_role") or "",
        "coin": row.get("coin"),
        "managed": bool(row.get("managed")),
        "lifecycleStatus": row.get("lifecycle_status") or "unknown",
        "createdAutomatically": bool(row.get("created_automatically")),
        "createdAt": _iso(row.get("created_at")),
        "updatedAt": _iso(row.get("updated_at")),
        "lastSeenAt": _iso(row.get("last_seen_at")),
        "retiredAt": _iso(row.get("retired_at")),
        "favorite": bool(row.get("favorite")),
        "notes": row.get("notes") or "",
        "tags": row.get("tags") or [],
        "location": row.get("location") or "",
        "rack": row.get("rack") or "",
        "position": row.get("position") or "",
        "manufacturer": row.get("manufacturer") or "",
        "model": row.get("model") or "",
        "serialNumber": row.get("serial_number") or "",
        "macAddress": legacy.get("macAddress") or "",
        "hostname": legacy.get("hostname") or "",
        "machineUuid": legacy.get("machineUuid") or "",
        "sshHostKey": legacy.get("sshHostKey") or "",
        "workerId": legacy.get("workerId") or "",
        "poolId": legacy.get("poolId") or "",
        "poolHost": legacy.get("poolHost") or "",
        "poolGroup": legacy.get("poolGroup") or "",
        "openPorts": legacy.get("openPorts") or [],
        "services": legacy.get("services") or [],
        "computeProfile": row.get("compute_profile") or {},
        "components": legacy.get("components") or [],
        "capabilities": row.get("capabilities") or [],
        "allocation": row.get("allocation") or {},
        "workloads": legacy.get("workloads") or [],
        "desiredState": row.get("desired_state") or {},
        "observedState": row.get("observed_state") or {},
        "operatingSystem": row.get("operating_system") or "",
        "architecture": row.get("architecture") or "",
        "hypervisor": row.get("hypervisor") or "",
        "containerRuntime": row.get("container_runtime") or "",
        "criticality": row.get("criticality") or "normal",
        "owner": row.get("owner") or "",
        "businessService": row.get("business_service") or "",
        "siteId": row.get("site_id") or "",
    }

def get_asset(asset_id: str) -> dict[str, Any] | None:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(_select_sql("WHERE a.asset_id = %s"), (asset_id,))
            row = cursor.fetchone()
    return _row_to_asset(dict(row)) if row else None

def list_assets(
    *, search: str | None = None, asset_type: str | None = None,
    lifecycle_status: str | None = None, managed: bool | None = None,
    favorite: bool | None = None, site_id: str | None = None,
    limit: int = 500, offset: int = 0,
) -> list[dict[str, Any]]:
    predicates: list[str] = []
    values: list[Any] = []
    if search:
        pattern = f"%{search.strip()}%"
        predicates.append("""
            (a.asset_id ILIKE %s OR a.name ILIKE %s OR
             a.friendly_name ILIKE %s OR a.display_name ILIKE %s OR
             a.primary_role ILIKE %s OR a.manufacturer ILIKE %s OR
             a.model ILIKE %s OR a.serial_number ILIKE %s OR
             addr.address ILIKE %s)
        """)
        values.extend([pattern] * 9)

    for column, value in [
        ("a.asset_type", asset_type),
        ("a.lifecycle_status", lifecycle_status),
        ("a.managed", managed),
        ("a.favorite", favorite),
        ("a.site_id", site_id),
    ]:
        if value is not None and value != "":
            predicates.append(f"{column} = %s")
            values.append(value)

    where = "WHERE " + " AND ".join(predicates) if predicates else ""
    values.extend([max(1, min(int(limit), 5000)), max(0, int(offset))])
    query = _select_sql(where) + """
        ORDER BY a.friendly_name, a.asset_id
        LIMIT %s OFFSET %s
    """
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, values)
            rows = cursor.fetchall()
    return [_row_to_asset(dict(row)) for row in rows]

def count_assets() -> int:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS count FROM nexus.assets")
            row = cursor.fetchone()
    return int((row or {}).get("count", 0))

def summary() -> dict[str, Any]:
    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) AS asset_count,
                       COUNT(*) FILTER (WHERE managed) AS managed_count,
                       COUNT(*) FILTER (WHERE favorite) AS favorite_count
                FROM nexus.assets
            """)
            totals = dict(cursor.fetchone() or {})
            cursor.execute("""
                SELECT asset_type, COUNT(*) AS count
                FROM nexus.assets GROUP BY asset_type ORDER BY asset_type
            """)
            by_type = {r["asset_type"]: int(r["count"]) for r in cursor.fetchall()}
            cursor.execute("""
                SELECT lifecycle_status, COUNT(*) AS count
                FROM nexus.assets GROUP BY lifecycle_status
                ORDER BY lifecycle_status
            """)
            by_lifecycle = {
                r["lifecycle_status"]: int(r["count"])
                for r in cursor.fetchall()
            }
    return {
        "assetCount": int(totals.get("asset_count", 0)),
        "managedAssetCount": int(totals.get("managed_count", 0)),
        "favoriteCount": int(totals.get("favorite_count", 0)),
        "byType": by_type,
        "byLifecycle": by_lifecycle,
    }
