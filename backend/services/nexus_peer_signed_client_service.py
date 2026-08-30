"""Build signed outbound requests for verified Nexus peers.

This module constructs authenticated peer requests only.
It deliberately performs no network I/O.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from backend.services import nexus_instance_service
from backend.services import nexus_peer_machine_identity_service
from backend.services import nexus_peer_pairing_service
from backend.services import nexus_peer_request_auth_service


PEER_STATUS_PATH = "/api/nexus/peer/status"


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def peer_status_url(
    peer_base_url: str,
) -> str:
    """Return the canonical peer-status URL."""

    base_url = (
        nexus_peer_pairing_service
        .normalize_peer_base_url(
            peer_base_url
        )
    )

    return (
        base_url.rstrip("/")
        + PEER_STATUS_PATH
    )


def _local_instance_id() -> str:
    local = (
        nexus_instance_service
        .get_local_instance()
    )

    if not local:
        raise RuntimeError(
            "Local Nexus instance is not registered"
        )

    instance_id = _text(
        local.get("instance_id")
    )

    if not instance_id:
        raise RuntimeError(
            "Local Nexus instance ID is missing"
        )

    return instance_id


def build_signed_peer_status_request(
    *,
    peer: dict[str, Any],
    timestamp: datetime | str | None = None,
    nonce: str | None = None,
) -> dict[str, Any]:
    """Build one signed GET request for peer status.

    The returned object contains transport metadata only.
    No network request is made here.
    """

    if not isinstance(peer, dict):
        raise ValueError(
            "peer must be an object"
        )

    remote_instance_id = _text(
        peer.get("remote_instance_id")
    )

    peer_base_url = _text(
        peer.get("peer_base_url")
    )

    if not remote_instance_id:
        raise ValueError(
            "Peer remote_instance_id is required"
        )

    if not peer_base_url:
        raise ValueError(
            "Peer peer_base_url is required"
        )

    if _text(peer.get("status")) != "verified":
        raise PermissionError(
            "Peer is not verified"
        )

    if peer.get("enabled") is not True:
        raise PermissionError(
            "Peer is not enabled"
        )

    local_instance_id = _local_instance_id()

    peer_local_instance_id = _text(
        peer.get("local_instance_id")
    )

    if (
        peer_local_instance_id
        and peer_local_instance_id
        != local_instance_id
    ):
        raise PermissionError(
            "Peer does not belong to local Nexus"
        )

    if remote_instance_id == local_instance_id:
        raise ValueError(
            "Cannot send a peer request to local Nexus"
        )

    url = peer_status_url(
        peer_base_url
    )

    parsed = urlparse(url)

    if (
        parsed.path != PEER_STATUS_PATH
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "Peer status URL is not canonical"
        )

    body = b""

    timestamp_value = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        if timestamp is None
        else timestamp
    )

    signed = (
        nexus_peer_request_auth_service
        .sign_request(
            method="GET",
            path=PEER_STATUS_PATH,
            sender_instance_id=local_instance_id,
            target_instance_id=remote_instance_id,
            timestamp=timestamp_value,
            body=body,
            nonce=nonce,
        )
    )

    headers = {
        nexus_peer_request_auth_service
        .HEADER_PROTOCOL:
            signed["protocol"],

        nexus_peer_request_auth_service
        .HEADER_ALGORITHM:
            signed["algorithm"],

        nexus_peer_request_auth_service
        .HEADER_SENDER:
            signed["senderInstanceId"],

        nexus_peer_request_auth_service
        .HEADER_TARGET:
            signed["targetInstanceId"],

        nexus_peer_request_auth_service
        .HEADER_TIMESTAMP:
            signed["timestamp"],

        nexus_peer_request_auth_service
        .HEADER_NONCE:
            signed["nonce"],

        nexus_peer_request_auth_service
        .HEADER_BODY_SHA256:
            signed["bodySha256"],

        nexus_peer_request_auth_service
        .HEADER_SIGNATURE:
            signed["signature"],
    }

    if set(headers) != set(
        nexus_peer_request_auth_service
        .AUTH_HEADERS
    ):
        raise RuntimeError(
            "Outbound Nexus peer auth header contract mismatch"
        )

    return {
        "method": "GET",
        "url": url,
        "path": PEER_STATUS_PATH,
        "headers": headers,
        "body": body,
        "localInstanceId": local_instance_id,
        "remoteInstanceId": remote_instance_id,
    }

DEFAULT_TIMEOUT_SECONDS = 10
MAX_RESPONSE_BODY_BYTES = 64 * 1024


def _decode_json_response(
    raw: bytes,
) -> dict[str, Any]:
    if not isinstance(raw, bytes):
        raise RuntimeError(
            "Nexus peer response body must be bytes"
        )

    if len(raw) > MAX_RESPONSE_BODY_BYTES:
        raise RuntimeError(
            "Nexus peer response body is too large"
        )

    try:
        payload = __import__("json").loads(
            raw.decode("utf-8")
        )
    except Exception as exc:
        raise RuntimeError(
            "Nexus peer returned invalid JSON"
        ) from exc

    if not isinstance(payload, dict):
        raise RuntimeError(
            "Nexus peer response must be an object"
        )

    return payload


def fetch_peer_status(
    *,
    peer: dict[str, Any],
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    timestamp: datetime | str | None = None,
    nonce: str | None = None,
) -> dict[str, Any]:
    """Execute one signed peer-status request."""

    if isinstance(timeout, bool):
        raise ValueError(
            "timeout must be a positive number"
        )

    try:
        timeout_value = float(timeout)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "timeout must be a positive number"
        ) from exc

    if (
        timeout_value <= 0
        or timeout_value > 60
    ):
        raise ValueError(
            "timeout must be greater than 0 "
            "and no more than 60 seconds"
        )

    outbound = build_signed_peer_status_request(
        peer=peer,
        timestamp=timestamp,
        nonce=nonce,
    )

    request = Request(
        outbound["url"],
        data=None,
        headers=outbound["headers"],
        method=outbound["method"],
    )

    try:
        with urlopen(
            request,
            timeout=timeout_value,
        ) as response:
            status = int(
                response.getcode()
            )

            raw = response.read(
                MAX_RESPONSE_BODY_BYTES + 1
            )

    except HTTPError as exc:
        try:
            raw = exc.read(
                MAX_RESPONSE_BODY_BYTES + 1
            )
        except Exception:
            raw = b""

        if len(raw) > MAX_RESPONSE_BODY_BYTES:
            raise RuntimeError(
                "Nexus peer error response is too large"
            ) from exc

        # Remote authentication/error details are deliberately
        # not propagated through the outbound client.
        raise RuntimeError(
            f"Nexus peer returned HTTP {exc.code}"
        ) from exc

    except URLError as exc:
        reason = _text(
            getattr(exc, "reason", "")
        )

        message = (
            "Nexus peer transport failed"
        )

        if reason:
            message += f": {reason}"

        raise RuntimeError(
            message
        ) from exc

    except TimeoutError as exc:
        raise RuntimeError(
            "Nexus peer transport timed out"
        ) from exc

    if status != 200:
        raise RuntimeError(
            f"Nexus peer returned HTTP {status}"
        )

    payload = _decode_json_response(
        raw
    )

    if payload.get("status") != "ok":
        raise RuntimeError(
            "Nexus peer returned unsuccessful status"
        )

    if payload.get("authenticated") is not True:
        raise RuntimeError(
            "Nexus peer did not confirm authentication"
        )

    peer_payload = payload.get("peer")

    if not isinstance(peer_payload, dict):
        raise RuntimeError(
            "Nexus peer response is missing peer identity"
        )

    expected_remote = outbound[
        "remoteInstanceId"
    ]

    returned_remote = _text(
        peer_payload.get(
            "remoteInstanceId"
        )
    )

    # The server reports the authenticated caller here.
    # That must equal our local Nexus instance.
    if (
        returned_remote
        != outbound["localInstanceId"]
    ):
        raise RuntimeError(
            "Nexus peer response authenticated "
            "the wrong caller identity"
        )

    returned_fingerprint = _text(
        peer_payload.get(
            "publicKeyFingerprint"
        )
    )

    local_identity = (
        nexus_peer_machine_identity_service
        .local_public_identity()
    )

    local_fingerprint = _text(
        local_identity.get("fingerprint")
    )

    if (
        not returned_fingerprint
        or not local_fingerprint
        or returned_fingerprint
        != local_fingerprint
    ):
        raise RuntimeError(
            "Nexus peer response authenticated "
            "the wrong machine identity"
        )

    capabilities = payload.get(
        "capabilities"
    )

    if not isinstance(capabilities, dict):
        raise RuntimeError(
            "Nexus peer response is missing capabilities"
        )

    if capabilities.get(
        "peerAwareness"
    ) is not True:
        raise RuntimeError(
            "Nexus peer awareness is not enabled"
        )

    for capability in (
        "federation",
        "cmdbExchange",
        "discoveryExchange",
        "management",
        "authorityDelegation",
    ):
        if capabilities.get(
            capability
        ) is not False:
            raise RuntimeError(
                "Nexus peer returned an unexpected "
                f"capability state: {capability}"
            )

    return {
        "status": "ok",
        "authenticated": True,
        "peerId": _text(
            peer_payload.get("peerId")
        ),
        "localInstanceId":
            outbound["localInstanceId"],
        "remoteInstanceId":
            expected_remote,
        "authenticatedCallerInstanceId":
            returned_remote,
        "publicKeyFingerprint": _text(
            peer_payload.get(
                "publicKeyFingerprint"
            )
        ),
        "capabilities": {
            "peerAwareness": True,
            "federation": False,
            "cmdbExchange": False,
            "discoveryExchange": False,
            "management": False,
            "authorityDelegation": False,
        },
    }
