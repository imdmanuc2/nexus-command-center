"""Controlled Nexus-to-Nexus peer pairing orchestration.

This service performs a transient authenticated identity handshake and
persists only the verified peer identity. Peer authentication
credentials are never persisted here or in the Nexus peer registry.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import (
    ProxyHandler,
    Request,
    build_opener,
)

from backend.db.repositories import nexus_peer_repository
from backend.services import nexus_peer_settings_service


IDENTITY_PATH = "/api/nexus/identity"

SUPPORTED_PROTOCOL_NAME = "seymour-nexus-peer"
SUPPORTED_PROTOCOL_VERSION = "1"

DEFAULT_TIMEOUT_SECONDS = 8


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _require_pairing_enabled() -> dict[str, Any]:
    settings = nexus_peer_repository.get_local_peer_settings()

    if not settings:
        raise RuntimeError(
            "Local peer settings are not initialized"
        )

    if not bool(settings.get("allow_peer_connections")):
        raise PermissionError(
            "Nexus peer connections are disabled"
        )

    return settings


def normalize_peer_base_url(
    value: str,
) -> str:
    """Validate and normalize a Nexus peer transport base URL."""

    raw = _text(value)

    if not raw:
        raise ValueError("peerBaseUrl is required")

    parsed = urlparse(raw)

    if parsed.scheme not in {"http", "https"}:
        raise ValueError(
            "peerBaseUrl must use http or https"
        )

    if not parsed.hostname:
        raise ValueError(
            "peerBaseUrl hostname is required"
        )

    if parsed.username or parsed.password:
        raise ValueError(
            "peerBaseUrl must not contain credentials"
        )

    if parsed.query or parsed.fragment:
        raise ValueError(
            "peerBaseUrl must not contain query or fragment"
        )

    if parsed.path not in {"", "/"}:
        raise ValueError(
            "peerBaseUrl must not contain an API path"
        )

    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError(
            "peerBaseUrl contains an invalid port"
        ) from exc

    host = parsed.hostname

    if ":" in host and not host.startswith("["):
        host = f"[{host}]"

    netloc = host

    if port is not None:
        netloc += f":{port}"

    return f"{parsed.scheme}://{netloc}"


def identity_url(
    peer_base_url: str,
) -> str:
    return (
        normalize_peer_base_url(peer_base_url)
        + IDENTITY_PATH
    )


def fetch_peer_identity(
    *,
    peer_base_url: str,
    credential: str,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Fetch an authenticated peer identity without persisting secrets."""

    _require_pairing_enabled()

    token = _text(credential)

    if not token:
        raise ValueError(
            "Peer authentication credential is required"
        )

    if not isinstance(timeout_seconds, int):
        raise ValueError(
            "timeoutSeconds must be an integer"
        )

    if timeout_seconds < 1 or timeout_seconds > 30:
        raise ValueError(
            "timeoutSeconds must be between 1 and 30"
        )

    url = identity_url(peer_base_url)

    request = Request(
        url,
        method="GET",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
    )

    # Ignore ambient HTTP proxy configuration. Peer transport addresses
    # are explicit Nexus endpoints and must be contacted directly.
    opener = build_opener(
        ProxyHandler({})
    )

    try:
        with opener.open(
            request,
            timeout=timeout_seconds,
        ) as response:
            status = int(response.status)
            raw = response.read()

    except HTTPError as exc:
        if exc.code == 401:
            raise PermissionError(
                "Peer authentication failed"
            ) from exc

        raise RuntimeError(
            f"Peer identity request failed with HTTP {exc.code}"
        ) from exc

    except URLError as exc:
        raise ConnectionError(
            "Peer transport is unreachable"
        ) from exc

    except TimeoutError as exc:
        raise TimeoutError(
            "Peer identity request timed out"
        ) from exc

    if status != 200:
        raise RuntimeError(
            f"Peer identity request returned HTTP {status}"
        )

    try:
        document = json.loads(raw.decode("utf-8"))
    except Exception as exc:
        raise ValueError(
            "Peer identity response is not valid JSON"
        ) from exc

    if not isinstance(document, dict):
        raise ValueError(
            "Peer identity response must be an object"
        )

    return document


def _validate_identity_document(
    document: dict[str, Any],
) -> None:
    if document.get("status") != "ok":
        raise ValueError(
            "Peer identity status must be ok"
        )

    protocol = document.get("protocol")

    if not isinstance(protocol, dict):
        raise ValueError(
            "Peer protocol document is missing"
        )

    if (
        _text(protocol.get("name"))
        != SUPPORTED_PROTOCOL_NAME
    ):
        raise ValueError(
            "Unsupported Nexus peer protocol"
        )

    if (
        _text(protocol.get("version"))
        != SUPPORTED_PROTOCOL_VERSION
    ):
        raise ValueError(
            "Unsupported Nexus peer protocol version"
        )

    instance = document.get("instance")

    if not isinstance(instance, dict):
        raise ValueError(
            "Peer instance document is missing"
        )

    if not _text(instance.get("instanceId")):
        raise ValueError(
            "Remote instanceId is required"
        )

    capabilities = document.get("capabilities")

    if not isinstance(capabilities, dict):
        raise ValueError(
            "Peer capabilities document is missing"
        )

    expected = {
        "peerAwareness": True,
        "federation": False,
        "cmdbExchange": False,
        "discoveryExchange": False,
        "management": False,
        "authorityDelegation": False,
    }

    for key, required_value in expected.items():
        if capabilities.get(key) is not required_value:
            raise ValueError(
                "Peer capability contract rejected: "
                + key
            )


def pair_peer(
    *,
    peer_base_url: str,
    credential: str,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Authenticate, validate, and remember a Nexus peer."""

    settings = _require_pairing_enabled()

    normalized_url = normalize_peer_base_url(
        peer_base_url
    )

    document = fetch_peer_identity(
        peer_base_url=normalized_url,
        credential=credential,
        timeout_seconds=timeout_seconds,
    )

    _validate_identity_document(document)

    instance = document["instance"]

    remote_instance_id = _text(
        instance.get("instanceId")
    )

    local_instance_id = _text(
        settings.get("instance_id")
    )

    if remote_instance_id == local_instance_id:
        raise ValueError(
            "Cannot pair Nexus with itself"
        )

    peer_id = f"peer-{remote_instance_id}"

    result = (
        nexus_peer_settings_service
        .register_verified_peer(
            peer_id=peer_id,
            identity_document=document,
            peer_base_url=normalized_url,
        )
    )

    return {
        "status": "ok",
        "paired": True,
        "peer": result["peer"],
    }
