"""Read-only orchestration for automatically discovered Nexus systems."""

from __future__ import annotations

from typing import Any, Callable

from backend.services import nexus_discovery_candidate_service
from backend.services import nexus_mdns_transport_service
from backend.services import nexus_peer_settings_service


DEFAULT_BROWSE_SECONDS = 2.0
DEFAULT_FETCH_TIMEOUT = 12.0


def _local_instance_id(
    settings_payload: dict[str, Any],
) -> str:
    settings = settings_payload.get("settings") or {}

    return str(
        settings.get("instanceId") or ""
    ).strip()


def _connected_instance_ids(
    peers_payload: dict[str, Any],
) -> set[str]:
    peers = peers_payload.get("peers") or []

    return {
        str(
            peer.get("remoteInstanceId") or ""
        ).strip()
        for peer in peers
        if str(
            peer.get("remoteInstanceId") or ""
        ).strip()
    }


def available_systems(
    *,
    browse_seconds: float = DEFAULT_BROWSE_SECONDS,
    fetch_timeout: float = DEFAULT_FETCH_TIMEOUT,
    settings_reader: Callable[
        [], dict[str, Any]
    ] = nexus_peer_settings_service.get_settings,
    peers_reader: Callable[
        [], dict[str, Any]
    ] = nexus_peer_settings_service.list_peers,
    browser: Callable[..., list[dict[str, Any]]] = (
        nexus_mdns_transport_service
        .browse_service_observations
    ),
    resolver: Callable[..., list[dict[str, Any]]] = (
        nexus_discovery_candidate_service
        .candidates_from_locators
    ),
) -> dict[str, Any]:
    """Return verified but untrusted Nexus discovery candidates.

    This is a read-only staging view. It does not create observations,
    CMDB objects, peers, enrollments, trust, federation, management,
    discovery exchange, or authority.
    """

    settings_payload = settings_reader()
    settings = settings_payload.get("settings") or {}

    enabled = bool(
        settings.get("localDiscoveryEnabled")
    )

    if not enabled:
        return {
            "status": "ok",
            "enabled": False,
            "count": 0,
            "candidates": [],
        }

    local_instance_id = _local_instance_id(
        settings_payload
    )

    peers_payload = peers_reader()
    connected_ids = _connected_instance_ids(
        peers_payload
    )

    observations = browser(
        wait_seconds=browse_seconds,
    )

    candidates = resolver(
        observations,
        timeout=fetch_timeout,
    )

    available = []

    for candidate in candidates:
        instance_id = str(
            candidate.get("instanceId") or ""
        ).strip()

        if not instance_id:
            continue

        if (
            local_instance_id
            and instance_id == local_instance_id
        ):
            continue

        if instance_id in connected_ids:
            continue

        safe_candidate = {
            **candidate,
            "trusted": False,
            "capabilities": {
                "peerAwareness": False,
                "federation": False,
                "cmdbExchange": False,
                "discoveryExchange": False,
                "management": False,
                "authorityDelegation": False,
            },
        }

        available.append(safe_candidate)

    return {
        "status": "ok",
        "enabled": True,
        "count": len(available),
        "candidates": available,
    }
