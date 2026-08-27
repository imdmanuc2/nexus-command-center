"""Service layer for user-controlled Nexus peer connectivity."""

from __future__ import annotations

from typing import Any

from backend.db.repositories import nexus_peer_repository


def _serialize_settings(
    row: dict[str, Any] | None,
) -> dict[str, Any]:
    if not row:
        return {
            "instanceId": "",
            "allowPeerConnections": False,
        }

    return {
        "instanceId": str(
            row.get("instance_id") or ""
        ).strip(),
        "allowPeerConnections": bool(
            row.get("allow_peer_connections")
        ),
        "createdAt": row.get("created_at"),
        "updatedAt": row.get("updated_at"),
    }


def get_settings() -> dict[str, Any]:
    """Return local user-controlled peer settings."""

    row = nexus_peer_repository.get_local_peer_settings()

    return {
        "status": "ok",
        "settings": _serialize_settings(row),
        "capabilities": {
            "peerAwareness": True,
            "federation": False,
            "cmdbExchange": False,
            "discoveryExchange": False,
            "management": False,
            "authorityDelegation": False,
        },
    }


def set_allow_peer_connections(
    enabled: bool,
) -> dict[str, Any]:
    """Explicitly enable or disable Nexus peer connections."""

    if not isinstance(enabled, bool):
        raise ValueError(
            "allowPeerConnections must be a boolean"
        )

    row = (
        nexus_peer_repository
        .set_local_peer_connections_enabled(enabled)
    )

    return {
        "status": "ok",
        "settings": _serialize_settings(row),
        "capabilities": {
            "peerAwareness": True,
            "federation": False,
            "cmdbExchange": False,
            "discoveryExchange": False,
            "management": False,
            "authorityDelegation": False,
        },
    }


def list_peers() -> dict[str, Any]:
    """Return configured peers without exposing credentials."""

    rows = nexus_peer_repository.list_peers()

    peers = []

    for row in rows:
        peers.append({
            "peerId": row.get("peer_id"),
            "remoteInstanceId": row.get(
                "remote_instance_id"
            ),
            "organizationId": row.get(
                "organization_id"
            ),
            "siteId": row.get("site_id"),
            "name": row.get("name"),
            "hostname": row.get("hostname"),
            "peerBaseUrl": row.get("peer_base_url"),
            "protocol": {
                "name": row.get("protocol_name"),
                "version": row.get(
                    "protocol_version"
                ),
            },
            "status": row.get("status"),
            "enabled": bool(row.get("enabled")),
            "capabilities": {
                "peerAwareness": bool(
                    row.get("peer_awareness")
                ),
                "federation": False,
                "cmdbExchange": False,
                "discoveryExchange": False,
                "management": False,
                "authorityDelegation": False,
            },
            "lastVerifiedAt": row.get(
                "last_verified_at"
            ),
            "lastSeenAt": row.get("last_seen_at"),
        })

    return {
        "status": "ok",
        "count": len(peers),
        "peers": peers,
    }
