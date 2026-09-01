"""Authenticate signed enrollment requests from unpaired Nexus systems.

Unlike durable-peer authentication, the sender is not yet present in the
peer registry. Its Ed25519 identity therefore comes from the enrollment
request body and must prove possession before any pending enrollment is
created.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from backend.db.repositories import nexus_peer_request_nonce_repository
from backend.services import nexus_instance_service
from backend.services import nexus_peer_machine_identity_service
from backend.services import nexus_peer_request_auth_service


REPLAY_RETENTION_SECONDS = 300


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


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


def _normalized_headers(
    headers: Mapping[str, Any],
) -> dict[str, str]:
    if headers is None:
        raise PermissionError(
            "Nexus enrollment authentication headers are required"
        )

    auth_names = {
        name.lower()
        for name in nexus_peer_request_auth_service.AUTH_HEADERS
    }

    result: dict[str, str] = {}

    get_all = getattr(headers, "get_all", None)

    if callable(get_all):
        for name in nexus_peer_request_auth_service.AUTH_HEADERS:
            values = get_all(name)

            if values is not None and len(values) > 1:
                raise PermissionError(
                    "Duplicate Nexus enrollment authentication header"
                )

    try:
        items = headers.items()
    except AttributeError as exc:
        raise PermissionError(
            "Nexus enrollment authentication headers are invalid"
        ) from exc

    for name, value in items:
        normalized_name = str(name).strip().lower()

        if not normalized_name:
            continue

        if (
            normalized_name in auth_names
            and normalized_name in result
        ):
            raise PermissionError(
                "Duplicate Nexus enrollment authentication header"
            )

        result[normalized_name] = _text(value)

    return result


def _required_header(
    headers: dict[str, str],
    name: str,
) -> str:
    value = headers.get(name.lower(), "")

    if not value:
        raise PermissionError(
            f"Missing enrollment authentication header: {name}"
        )

    return value


def authenticate_enrollment_request(
    *,
    method: str,
    path: str,
    headers: Mapping[str, Any],
    body: bytes,
    payload: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Verify one unpaired enrollment request and claim its nonce."""

    if not isinstance(body, bytes):
        raise TypeError("body must be bytes")

    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")

    local_instance_id = _local_instance_id()
    normalized = _normalized_headers(headers)

    protocol = _required_header(
        normalized,
        nexus_peer_request_auth_service.HEADER_PROTOCOL,
    )
    algorithm = _required_header(
        normalized,
        nexus_peer_request_auth_service.HEADER_ALGORITHM,
    )
    sender_instance_id = _required_header(
        normalized,
        nexus_peer_request_auth_service.HEADER_SENDER,
    )
    target_instance_id = _required_header(
        normalized,
        nexus_peer_request_auth_service.HEADER_TARGET,
    )
    timestamp = _required_header(
        normalized,
        nexus_peer_request_auth_service.HEADER_TIMESTAMP,
    )
    nonce = _required_header(
        normalized,
        nexus_peer_request_auth_service.HEADER_NONCE,
    )
    supplied_digest = _required_header(
        normalized,
        nexus_peer_request_auth_service.HEADER_BODY_SHA256,
    )
    signature = _required_header(
        normalized,
        nexus_peer_request_auth_service.HEADER_SIGNATURE,
    )

    nexus_peer_request_auth_service.validate_protocol(protocol)
    nexus_peer_request_auth_service.validate_algorithm(algorithm)

    normalized_method = (
        nexus_peer_request_auth_service.normalize_method(method)
    )
    normalized_path = (
        nexus_peer_request_auth_service.normalize_path(path)
    )
    normalized_nonce = (
        nexus_peer_request_auth_service.normalize_nonce(nonce)
    )

    if target_instance_id != local_instance_id:
        raise PermissionError(
            "Enrollment authentication target does not match local Nexus"
        )

    if sender_instance_id == local_instance_id:
        raise PermissionError(
            "Local Nexus cannot enroll itself"
        )

    payload_instance_id = _text(
        payload.get("remoteInstanceId")
    )
    payload_algorithm = _text(
        payload.get("publicKeyAlgorithm")
    )
    public_key = _text(
        payload.get("publicKey")
    )
    supplied_fingerprint = _text(
        payload.get("publicKeyFingerprint")
    )

    if payload_instance_id != sender_instance_id:
        raise PermissionError(
            "Enrollment sender identity does not match signed request"
        )

    if payload_algorithm != algorithm:
        raise PermissionError(
            "Enrollment machine algorithm does not match signed request"
        )

    if (
        not public_key
        or not supplied_fingerprint
    ):
        raise PermissionError(
            "Enrollment machine identity is required"
        )

    try:
        raw_public_key = (
            nexus_peer_machine_identity_service
            .decode_public_key(public_key)
        )

        calculated_fingerprint = (
            nexus_peer_machine_identity_service
            .public_key_fingerprint(raw_public_key)
        )
    except (TypeError, ValueError) as exc:
        raise PermissionError(
            "Enrollment machine identity is invalid"
        ) from exc

    if calculated_fingerprint != supplied_fingerprint:
        raise PermissionError(
            "Enrollment machine identity fingerprint mismatch"
        )

    calculated_digest = (
        nexus_peer_request_auth_service.body_sha256(body)
    )

    if supplied_digest.lower() != calculated_digest:
        raise PermissionError(
            "Enrollment authentication body digest mismatch"
        )

    normalized_timestamp = (
        nexus_peer_request_auth_service
        .validate_timestamp_freshness(
            timestamp,
            now=now,
        )
    )

    try:
        verified = (
            nexus_peer_request_auth_service
            .verify_signature(
                public_key=public_key,
                protocol=protocol,
                algorithm=algorithm,
                method=normalized_method,
                path=normalized_path,
                sender_instance_id=sender_instance_id,
                target_instance_id=target_instance_id,
                timestamp=normalized_timestamp,
                nonce=normalized_nonce,
                body_sha256_value=calculated_digest,
                signature=signature,
            )
        )
    except (TypeError, ValueError) as exc:
        raise PermissionError(
            "Enrollment authentication signature is invalid"
        ) from exc

    if not verified:
        raise PermissionError(
            "Enrollment authentication signature is invalid"
        )

    request_timestamp = (
        nexus_peer_request_auth_service
        .timestamp_datetime(normalized_timestamp)
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

    current = current.astimezone(timezone.utc)

    expires_at = current + timedelta(
        seconds=REPLAY_RETENTION_SECONDS
    )

    if expires_at <= request_timestamp:
        expires_at = request_timestamp + timedelta(
            seconds=REPLAY_RETENTION_SECONDS
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
            "Enrollment authentication replay detected"
        )

    return {
        "authenticated": True,
        "localInstanceId": local_instance_id,
        "remoteInstanceId": sender_instance_id,
        "algorithm": algorithm,
        "publicKeyFingerprint": supplied_fingerprint,
    }
