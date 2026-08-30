"""Authenticate signed requests from durable verified Nexus peers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from backend.db.repositories import nexus_peer_repository
from backend.db.repositories import nexus_peer_request_nonce_repository
from backend.services import nexus_instance_service
from backend.services import nexus_peer_machine_identity_service
from backend.services import nexus_peer_request_auth_service


REPLAY_RETENTION_SECONDS = 300


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _header_map(
    headers: Mapping[str, Any],
) -> dict[str, str]:
    """Normalize headers while rejecting auth-header ambiguity."""

    if headers is None:
        raise PermissionError(
            "Nexus peer authentication headers are required"
        )

    auth_names = {
        name.lower()
        for name in nexus_peer_request_auth_service.AUTH_HEADERS
    }

    result: dict[str, str] = {}

    # HTTPMessage, used by BaseHTTPRequestHandler, preserves
    # duplicate field occurrences and exposes them via get_all().
    get_all = getattr(
        headers,
        "get_all",
        None,
    )

    if callable(get_all):
        for auth_name in (
            nexus_peer_request_auth_service.AUTH_HEADERS
        ):
            values = get_all(
                auth_name
            )

            if values is not None and len(values) > 1:
                raise PermissionError(
                    "Duplicate Nexus peer authentication header"
                )

    try:
        items = headers.items()
    except AttributeError as exc:
        raise PermissionError(
            "Nexus peer authentication headers are invalid"
        ) from exc

    for name, value in items:
        normalized_name = str(
            name
        ).strip().lower()

        if not normalized_name:
            continue

        if (
            normalized_name in auth_names
            and normalized_name in result
        ):
            raise PermissionError(
                "Duplicate Nexus peer authentication header"
            )

        result[normalized_name] = (
            "" if value is None
            else str(value).strip()
        )

    return result

def _required_header(
    headers: dict[str, str],
    name: str,
) -> str:
    value = headers.get(
        name.lower(),
        "",
    )

    if not value:
        raise PermissionError(
            f"Missing peer authentication header: {name}"
        )

    return value


def _local_instance_id() -> str:
    local = nexus_instance_service.get_local_instance()

    if not local:
        raise RuntimeError(
            "Local Nexus instance is not registered"
        )

    instance_id = _text(
        local.get("instance_id")
        or local.get("instanceId")
    )

    if not instance_id:
        raise RuntimeError(
            "Local Nexus instance identity is invalid"
        )

    return instance_id


def _require_verified_peer(
    *,
    local_instance_id: str,
    remote_instance_id: str,
) -> dict[str, Any]:
    peer = nexus_peer_repository.get_peer_by_instances(
        local_instance_id=local_instance_id,
        remote_instance_id=remote_instance_id,
    )

    if not peer:
        raise PermissionError(
            "Nexus peer is not registered"
        )

    if _text(peer.get("status")) != "verified":
        raise PermissionError(
            "Nexus peer is not verified"
        )

    if peer.get("enabled") is not True:
        raise PermissionError(
            "Nexus peer is disabled"
        )

    algorithm = _text(
        peer.get("public_key_algorithm")
    )
    public_key = _text(
        peer.get("public_key")
    )
    fingerprint = _text(
        peer.get("public_key_fingerprint")
    )

    if not algorithm or not public_key or not fingerprint:
        raise PermissionError(
            "Nexus peer has no bound machine identity"
        )

    nexus_peer_request_auth_service.validate_algorithm(
        algorithm
    )

    try:
        raw_public_key = (
            nexus_peer_machine_identity_service
            .decode_public_key(public_key)
        )

        calculated = (
            nexus_peer_machine_identity_service
            .public_key_fingerprint(raw_public_key)
        )
    except (TypeError, ValueError) as exc:
        raise PermissionError(
            "Nexus peer machine identity is invalid"
        ) from exc

    if calculated != fingerprint:
        raise PermissionError(
            "Nexus peer machine identity fingerprint mismatch"
        )

    return peer


def authenticate_request(
    *,
    method: str,
    path: str,
    headers: Mapping[str, Any],
    body: bytes,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Authenticate one signed request from a durable Nexus peer.

    Replay state is claimed only after every other authentication
    check has succeeded.
    """

    if not isinstance(body, bytes):
        raise TypeError("body must be bytes")

    local_instance_id = _local_instance_id()
    normalized_headers = _header_map(headers)

    protocol = _required_header(
        normalized_headers,
        nexus_peer_request_auth_service.HEADER_PROTOCOL,
    )
    algorithm = _required_header(
        normalized_headers,
        nexus_peer_request_auth_service.HEADER_ALGORITHM,
    )
    sender_instance_id = _required_header(
        normalized_headers,
        nexus_peer_request_auth_service.HEADER_SENDER,
    )
    target_instance_id = _required_header(
        normalized_headers,
        nexus_peer_request_auth_service.HEADER_TARGET,
    )
    timestamp = _required_header(
        normalized_headers,
        nexus_peer_request_auth_service.HEADER_TIMESTAMP,
    )
    nonce = _required_header(
        normalized_headers,
        nexus_peer_request_auth_service.HEADER_NONCE,
    )
    supplied_body_sha256 = _required_header(
        normalized_headers,
        nexus_peer_request_auth_service.HEADER_BODY_SHA256,
    )
    signature = _required_header(
        normalized_headers,
        nexus_peer_request_auth_service.HEADER_SIGNATURE,
    )

    nexus_peer_request_auth_service.validate_protocol(
        protocol
    )
    nexus_peer_request_auth_service.validate_algorithm(
        algorithm
    )

    normalized_method = (
        nexus_peer_request_auth_service
        .normalize_method(method)
    )
    normalized_path = (
        nexus_peer_request_auth_service
        .normalize_path(path)
    )
    normalized_nonce = (
        nexus_peer_request_auth_service
        .normalize_nonce(nonce)
    )

    if target_instance_id != local_instance_id:
        raise PermissionError(
            "Peer authentication target does not match local Nexus"
        )

    if sender_instance_id == local_instance_id:
        raise PermissionError(
            "Local Nexus cannot authenticate as a remote peer"
        )

    peer = _require_verified_peer(
        local_instance_id=local_instance_id,
        remote_instance_id=sender_instance_id,
    )

    # The algorithm is both signed and bound to the durable peer.
    if (
        _text(peer.get("public_key_algorithm"))
        != algorithm
    ):
        raise PermissionError(
            "Peer authentication algorithm does not match "
            "registered machine identity"
        )

    calculated_body_sha256 = (
        nexus_peer_request_auth_service
        .body_sha256(body)
    )

    if supplied_body_sha256.lower() != calculated_body_sha256:
        raise PermissionError(
            "Peer authentication body digest mismatch"
        )

    normalized_timestamp = (
        nexus_peer_request_auth_service
        .validate_timestamp_freshness(
            timestamp,
            now=now,
        )
    )

    verified = (
        nexus_peer_request_auth_service
        .verify_signature(
            public_key=_text(peer["public_key"]),
            protocol=protocol,
            algorithm=algorithm,
            method=normalized_method,
            path=normalized_path,
            sender_instance_id=sender_instance_id,
            target_instance_id=target_instance_id,
            timestamp=normalized_timestamp,
            nonce=normalized_nonce,
            body_sha256_value=calculated_body_sha256,
            signature=signature,
        )
    )

    if not verified:
        raise PermissionError(
            "Peer authentication signature is invalid"
        )

    request_timestamp = (
        nexus_peer_request_auth_service
        .timestamp_datetime(
            normalized_timestamp
        )
    )

    current = (
        datetime.now(timezone.utc)
        if now is None
        else now
    )

    if current.tzinfo is None:
        raise ValueError(
            "now must include timezone"
        )

    current = current.astimezone(
        timezone.utc
    )

    # Expiry is based on verification time rather than request time.
    # This safely covers accepted future timestamps within clock skew.
    expires_at = current + timedelta(
        seconds=REPLAY_RETENTION_SECONDS
    )

    if expires_at <= request_timestamp:
        expires_at = (
            request_timestamp
            + timedelta(
                seconds=REPLAY_RETENTION_SECONDS
            )
        )

    claimed = (
        nexus_peer_request_nonce_repository
        .claim_nonce(
            local_instance_id=local_instance_id,
            remote_instance_id=sender_instance_id,
            nonce=normalized_nonce,
            request_timestamp=request_timestamp,
            expires_at=expires_at,
        )
    )

    if not claimed:
        raise PermissionError(
            "Peer authentication replay detected"
        )

    return {
        "peerId": _text(peer.get("peer_id")),
        "localInstanceId": local_instance_id,
        "remoteInstanceId": sender_instance_id,
        "algorithm": algorithm,
        "publicKeyFingerprint": _text(
            peer.get("public_key_fingerprint")
        ),
        "authenticated": True,
    }
