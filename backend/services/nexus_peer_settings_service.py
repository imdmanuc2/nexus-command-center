"""Service layer for user-controlled Nexus peer connectivity."""

from __future__ import annotations

from typing import Any

from backend.db.repositories import nexus_peer_repository
from backend.services import nexus_local_discovery_state_service


def _serialize_settings(
    row: dict[str, Any] | None,
) -> dict[str, Any]:
    if not row:
        return {
            "instanceId": "",
            "allowPeerConnections": False,
            "localDiscoveryEnabled": False,
        }

    return {
        "instanceId": str(
            row.get("instance_id") or ""
        ).strip(),
        "allowPeerConnections": bool(
            row.get("allow_peer_connections")
        ),
        "localDiscoveryEnabled": bool(
            row.get("local_discovery_enabled")
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


def set_local_discovery_enabled(
    enabled: bool,
) -> dict[str, Any]:
    """Explicitly enable or disable local Nexus discovery."""

    if not isinstance(enabled, bool):
        raise ValueError(
            "localDiscoveryEnabled must be a boolean"
        )

    row = (
        nexus_peer_repository
        .set_local_discovery_enabled(enabled)
    )

    nexus_local_discovery_state_service.write_public_state(
        enabled
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


def register_verified_peer(
    *,
    peer_id: str,
    identity_document: dict[str, Any],
    peer_base_url: str,
) -> dict[str, Any]:
    """Remember an already authenticated Nexus peer.

    This function does not perform transport authentication itself and
    does not accept or store peer credentials. If an Ed25519 machine
    identity is supplied, its public key and fingerprint are validated
    before the durable peer record is written.
    """

    settings = (
        nexus_peer_repository
        .get_local_peer_settings()
    )

    if not settings:
        raise RuntimeError(
            "Local peer settings are not initialized"
        )

    if not bool(
        settings.get("allow_peer_connections")
    ):
        raise PermissionError(
            "Nexus peer connections are disabled"
        )

    if not isinstance(identity_document, dict):
        raise ValueError(
            "identityDocument must be an object"
        )

    if identity_document.get("status") != "ok":
        raise ValueError(
            "Peer identity status must be ok"
        )

    protocol = identity_document.get("protocol")

    if not isinstance(protocol, dict):
        raise ValueError(
            "Peer protocol document is missing"
        )

    if protocol.get("name") != "seymour-nexus-peer":
        raise ValueError(
            "Unsupported Nexus peer protocol"
        )

    if str(protocol.get("version") or "") != "1":
        raise ValueError(
            "Unsupported Nexus peer protocol version"
        )

    instance = identity_document.get("instance")

    if not isinstance(instance, dict):
        raise ValueError(
            "Peer instance document is missing"
        )

    remote_instance_id = str(
        instance.get("instanceId") or ""
    ).strip()

    if not remote_instance_id:
        raise ValueError(
            "Remote instanceId is required"
        )

    local_instance_id = str(
        settings.get("instance_id") or ""
    ).strip()

    if remote_instance_id == local_instance_id:
        raise ValueError(
            "Cannot pair Nexus with itself"
        )

    capabilities = identity_document.get(
        "capabilities"
    )

    if not isinstance(capabilities, dict):
        raise ValueError(
            "Peer capabilities document is missing"
        )

    required_safe_capabilities = {
        "peerAwareness": True,
        "federation": False,
        "cmdbExchange": False,
        "discoveryExchange": False,
        "management": False,
        "authorityDelegation": False,
    }

    for key, expected in (
        required_safe_capabilities.items()
    ):
        if capabilities.get(key) is not expected:
            raise ValueError(
                "Peer capability contract rejected: "
                + key
            )

    peer_url = str(
        peer_base_url or ""
    ).strip()

    if not peer_url:
        raise ValueError(
            "peerBaseUrl is required"
        )

    public_key_algorithm = ""
    public_key = ""
    public_key_fingerprint = ""

    machine_identity = identity_document.get(
        "machineIdentity"
    )

    if machine_identity is not None:
        if not isinstance(machine_identity, dict):
            raise ValueError(
                "Peer machineIdentity must be an object"
            )

        public_key_algorithm = str(
            machine_identity.get("algorithm") or ""
        ).strip()

        public_key = str(
            machine_identity.get("publicKey") or ""
        ).strip()

        public_key_fingerprint = str(
            machine_identity.get("fingerprint") or ""
        ).strip()

        key_parts = (
            public_key_algorithm,
            public_key,
            public_key_fingerprint,
        )

        populated_key_parts = sum(
            bool(value)
            for value in key_parts
        )

        if populated_key_parts not in {0, 3}:
            raise ValueError(
                "Peer machine identity must include "
                "algorithm, public key, and fingerprint together"
            )

        if public_key_algorithm:
            if public_key_algorithm != "Ed25519":
                raise ValueError(
                    "Unsupported peer machine-key algorithm"
                )

            from backend.services import (
                nexus_peer_machine_identity_service
            )

            raw_public_key = (
                nexus_peer_machine_identity_service
                .decode_public_key(
                    public_key
                )
            )

            expected_fingerprint = (
                nexus_peer_machine_identity_service
                .public_key_fingerprint(
                    raw_public_key
                )
            )

            if (
                public_key_fingerprint
                != expected_fingerprint
            ):
                raise ValueError(
                    "Peer public-key fingerprint mismatch"
                )

    row = nexus_peer_repository.upsert_verified_peer(
        peer_id=str(peer_id or "").strip(),
        local_instance_id=local_instance_id,
        remote_instance_id=remote_instance_id,
        organization_id=str(
            instance.get("organizationId") or ""
        ).strip(),
        site_id=str(
            instance.get("siteId") or ""
        ).strip(),
        name=str(
            instance.get("name") or ""
        ).strip(),
        hostname=str(
            instance.get("hostname") or ""
        ).strip(),
        peer_base_url=peer_url,
        protocol_name="seymour-nexus-peer",
        protocol_version="1",
        public_key_algorithm=public_key_algorithm,
        public_key=public_key,
        public_key_fingerprint=public_key_fingerprint,
        metadata={
            "identitySource": str(
                instance.get("identitySource")
                or ""
            ).strip(),
        },
    )

    return {
        "status": "ok",
        "peer": {
            "peerId": row["peer_id"],
            "remoteInstanceId":
                row["remote_instance_id"],
            "organizationId":
                row["organization_id"],
            "siteId": row["site_id"],
            "name": row["name"],
            "hostname": row["hostname"],
            "peerBaseUrl": row["peer_base_url"],
            "protocol": {
                "name": row["protocol_name"],
                "version":
                    row["protocol_version"],
            },
            "machineIdentity": {
                "algorithm":
                    row.get("public_key_algorithm")
                    or "",
                "publicKey":
                    row.get("public_key")
                    or "",
                "fingerprint":
                    row.get("public_key_fingerprint")
                    or "",
            },
            "status": row["status"],
            "enabled": bool(row["enabled"]),
            "capabilities": {
                "peerAwareness": True,
                "federation": False,
                "cmdbExchange": False,
                "discoveryExchange": False,
                "management": False,
                "authorityDelegation": False,
            },
            "lastVerifiedAt":
                row["last_verified_at"],
            "lastSeenAt": row["last_seen_at"],
        },
    }


def remove_peer(
    peer_id: str,
) -> dict[str, Any]:
    """Forget a configured Nexus peer."""

    deleted = nexus_peer_repository.delete_peer(
        peer_id
    )

    return {
        "status": "ok",
        "peerId": str(peer_id or "").strip(),
        "removed": deleted,
    }
