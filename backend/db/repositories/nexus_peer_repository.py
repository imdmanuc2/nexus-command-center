"""Repository for Nexus peer connection settings and peer registry."""

from __future__ import annotations

from typing import Any

from backend.db.connection import get_connection
from psycopg.types.json import Jsonb


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
                    public_key_algorithm,
                    public_key,
                    public_key_fingerprint,
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


def upsert_verified_peer(
    *,
    peer_id: str,
    local_instance_id: str,
    remote_instance_id: str,
    organization_id: str,
    site_id: str,
    name: str,
    hostname: str,
    peer_base_url: str,
    protocol_name: str,
    protocol_version: str,
    public_key_algorithm: str = "",
    public_key: str = "",
    public_key_fingerprint: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist one explicitly verified Nexus peer.

    Credentials are intentionally not accepted or stored here.
    """

    values = {
        "peer_id": _text(peer_id),
        "local_instance_id": _text(local_instance_id),
        "remote_instance_id": _text(remote_instance_id),
        "organization_id": _text(organization_id),
        "site_id": _text(site_id),
        "name": _text(name),
        "hostname": _text(hostname),
        "peer_base_url": _text(peer_base_url),
        "protocol_name": _text(protocol_name),
        "protocol_version": _text(protocol_version),
        "public_key_algorithm": _text(
            public_key_algorithm
        ),
        "public_key": _text(
            public_key
        ),
        "public_key_fingerprint": _text(
            public_key_fingerprint
        ),
    }

    required = [
        "peer_id",
        "local_instance_id",
        "remote_instance_id",
        "peer_base_url",
        "protocol_name",
        "protocol_version",
    ]

    missing = [
        key
        for key in required
        if not values[key]
    ]

    if missing:
        raise ValueError(
            "Missing peer field(s): "
            + ", ".join(missing)
        )

    if (
        values["remote_instance_id"]
        == values["local_instance_id"]
    ):
        raise ValueError(
            "Cannot register local Nexus as its own peer"
        )

    key_values = (
        values["public_key_algorithm"],
        values["public_key"],
        values["public_key_fingerprint"],
    )

    populated_key_values = sum(
        bool(value)
        for value in key_values
    )

    if populated_key_values not in {0, 3}:
        raise ValueError(
            "Peer public-key identity must include "
            "algorithm, public key, and fingerprint together"
        )

    if (
        values["public_key_algorithm"]
        and values["public_key_algorithm"] != "Ed25519"
    ):
        raise ValueError(
            "Unsupported peer public-key algorithm"
        )

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO nexus.nexus_peers (
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
                    public_key_algorithm,
                    public_key,
                    public_key_fingerprint,
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
                    updated_at
                )
                VALUES (
                    %(peer_id)s,
                    %(local_instance_id)s,
                    %(remote_instance_id)s,
                    %(organization_id)s,
                    %(site_id)s,
                    %(name)s,
                    %(hostname)s,
                    %(peer_base_url)s,
                    %(protocol_name)s,
                    %(protocol_version)s,
                    NULLIF(
                        %(public_key_algorithm)s,
                        ''
                    ),
                    NULLIF(
                        %(public_key)s,
                        ''
                    ),
                    NULLIF(
                        %(public_key_fingerprint)s,
                        ''
                    ),
                    'verified',
                    TRUE,
                    TRUE,
                    FALSE,
                    FALSE,
                    FALSE,
                    FALSE,
                    FALSE,
                    NOW(),
                    NOW(),
                    %(metadata)s,
                    NOW()
                )
                ON CONFLICT (
                    local_instance_id,
                    remote_instance_id
                )
                WHERE remote_instance_id IS NOT NULL
                DO UPDATE SET
                    organization_id =
                        EXCLUDED.organization_id,
                    site_id =
                        EXCLUDED.site_id,
                    name =
                        EXCLUDED.name,
                    hostname =
                        EXCLUDED.hostname,
                    peer_base_url =
                        EXCLUDED.peer_base_url,
                    protocol_name =
                        EXCLUDED.protocol_name,
                    protocol_version =
                        EXCLUDED.protocol_version,
                    public_key_algorithm =
                        COALESCE(
                            EXCLUDED.public_key_algorithm,
                            nexus.nexus_peers.public_key_algorithm
                        ),
                    public_key =
                        COALESCE(
                            EXCLUDED.public_key,
                            nexus.nexus_peers.public_key
                        ),
                    public_key_fingerprint =
                        COALESCE(
                            EXCLUDED.public_key_fingerprint,
                            nexus.nexus_peers.public_key_fingerprint
                        ),
                    status = 'verified',
                    enabled = TRUE,
                    peer_awareness = TRUE,
                    federation_enabled = FALSE,
                    cmdb_exchange_enabled = FALSE,
                    discovery_exchange_enabled = FALSE,
                    management_enabled = FALSE,
                    authority_delegation_enabled = FALSE,
                    last_verified_at = NOW(),
                    last_seen_at = NOW(),
                    metadata = EXCLUDED.metadata,
                    updated_at = NOW()
                RETURNING *
                """,
                {
                    **values,
                    "metadata": Jsonb(metadata or {}),
                },
            )

            result = dict(cursor.fetchone())

        connection.commit()

    return result


def delete_peer(
    peer_id: str,
) -> bool:
    """Remove one configured Nexus peer."""

    target = _text(peer_id)

    if not target:
        raise ValueError("peerId is required")

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DELETE FROM nexus.nexus_peers
                WHERE peer_id = %s
                """,
                (target,),
            )

            deleted = cursor.rowcount > 0

        connection.commit()

    return deleted
