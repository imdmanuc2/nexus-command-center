"""Public Nexus discovery identity.

This document identifies a Nexus installation for discovery only.
It grants no trust, enrollment, federation, CMDB exchange, discovery
exchange, management, or authority.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from backend.core.nexus_identity import runtime_identity
from backend.services import nexus_peer_machine_identity_service
from backend.services import nexus_peer_settings_service


DISCOVERY_SERVICE = "nexus-command-center"
DISCOVERY_VERSION = "1"
PEER_PROTOCOL_NAME = "seymour-nexus-peer"
PEER_PROTOCOL_VERSION = "1"


def discovery_enabled() -> bool:
    payload = nexus_peer_settings_service.get_settings()

    settings = payload.get("settings") or {}

    return bool(
        settings.get("localDiscoveryEnabled")
    )


@lru_cache(maxsize=1)
def _discovery_identity_document() -> dict[str, Any]:
    """Build immutable public identity for this peer process.

    Runtime instance identity and the peer machine key are stable for the
    lifetime of a Nexus peer process. Caching this document avoids repeated
    private-key file reads during discovery probes.

    The user-controlled discovery setting is intentionally NOT cached.
    """
    identity = runtime_identity()

    machine = (
        nexus_peer_machine_identity_service
        .local_public_identity(
            create=False
        )
    )

    return {
        "status": "ok",
        "service": DISCOVERY_SERVICE,
        "discoveryVersion": DISCOVERY_VERSION,
        "instance": {
            "instanceId": identity["instanceId"],
            "name": identity["instanceName"],
            "hostname": identity["hostname"],
        },
        "peerProtocol": {
            "name": PEER_PROTOCOL_NAME,
            "version": PEER_PROTOCOL_VERSION,
        },
        "machineIdentity": {
            "algorithm": machine["algorithm"],
            "publicKey": machine["publicKey"],
            "fingerprint": machine["fingerprint"],
        },
    }


def discovery_document() -> dict[str, Any]:
    if not discovery_enabled():
        raise PermissionError(
            "Nexus local discovery is disabled"
        )

    return dict(_discovery_identity_document())
