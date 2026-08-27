"""Repository for Nexus peer connection settings and peer registry."""

from __future__ import annotations

from typing import Any

from backend.db.connection import get_connection


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def get_local_peer_settings() -> dict[str, Any] | None:
    """Return peer connection settings for the local Nexus instance."""

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    s.instance_id,
                    s.allow_peer_connections,
                    s.created_at,
                    s.updated_at
                FROM nexus.nexus_peer_settings s
                JOIN nexus.nexus_instances i
                    ON i.instance_id = s.instance_id
                WHERE i.is_local = TRUE
                LIMIT 1
                """
            )

            row = cursor.fetchone()

    return dict(row) if row else None


def set_local_peer_connections_enabled(
    enabled: bool,
) -> dict[str, Any]:
    """Set whether this Nexus installation allows peer connections."""

    if not isinstance(enabled, bool):
        raise ValueError("enabled must be a boolean")

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT instance_id
                FROM nexus.nexus_instances
                WHERE is_local = TRUE
                LIMIT 1
                """
            )

            local = cursor.fetchone()

            if not local:
                raise RuntimeError(
                    "Local Nexus instance is not registered"
                )

            instance_id = _text(local["instance_id"])

            cursor.execute(
                """
                INSERT INTO nexus.nexus_peer_settings (
                    instance_id,
                    allow_peer_connections,
                    updated_at
                )
                VALUES (
                    %s,
                    %s,
                    NOW()
                )
                ON CONFLICT (instance_id)
                DO UPDATE SET
                    allow_peer_connections =
                        EXCLUDED.allow_peer_connections,
                    updated_at = NOW()
                RETURNING
                    instance_id,
                    allow_peer_connections,
                    created_at,
                    updated_at
                """,
                (
                    instance_id,
                    enabled,
                ),
            )

            result = dict(cursor.fetchone())

        connection.commit()

    return result


def list_peers() -> list[dict[str, Any]]:
    """Return configured Nexus peers."""

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    peer_id,
                    local_instance_id,
                    remote_instance_id,
                    organization_id,
                    site_id,
                    name,
                    hostname,
                    peer_base_url,
                    protocol_name,
                    protocol_version,
                    status,
                    enabled,
                    peer_awareness,
                    federation_enabled,
                    cmdb_exchange_enabled,
                    discovery_exchange_enabled,
                    management_enabled,
                    authority_delegation_enabled,
                    last_verified_at,
                    last_seen_at,
                    metadata,
                    created_at,
                    updated_at
                FROM nexus.nexus_peers
                ORDER BY name, peer_id
                """
            )

            rows = cursor.fetchall()

    return [dict(row) for row in rows]
