"""HTTP routes for authenticated Nexus peer protocol."""

from __future__ import annotations

import json
from urllib.parse import urlparse

from backend.services import nexus_peer_service


IDENTITY_PATH = "/api/nexus/identity"


def _send(handler, result, status=200) -> None:
    payload = json.dumps(
        result,
        default=str,
    ).encode("utf-8")

    handler._send_json(payload, status)


def handle_get(handler) -> bool:
    path = urlparse(handler.path).path

    if path != IDENTITY_PATH:
        return False

    status, result = nexus_peer_service.identity(
        handler.headers.get("Authorization", "")
    )

    _send(handler, result, status)
    return True
