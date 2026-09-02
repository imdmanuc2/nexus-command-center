"""Authenticate signed enrollment requests from unpaired Nexus systems.

Unlike durable-peer authentication, the sender is not yet present in the
peer registry. Its Ed25519 identity therefore comes from the enrollment
request body and must prove possession before any pending enrollment is
created.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Mapping

from backend.db.repositories import nexus_peer_enrollment_repository
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
    pairing_id = _text(
        payload.get("pairingId")
    )
    capability_hash = _text(
        payload.get("capabilityHash")
    ).lower()

    if not pairing_id:
        raise PermissionError(
            "Enrollment pairingId is required"
        )

    if (
        len(capability_hash) != 64
        or any(
            character not in "0123456789abcdef"
            for character in capability_hash
        )
    ):
        raise PermissionError(
            "Enrollment capabilityHash is invalid"
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

def authenticate_enrollment_completion(
    *,
    method: str,
    path: str,
    headers: Mapping[str, Any],
    body: bytes,
    payload: dict[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    """Authenticate pairing completion using stored requester identity.

    Unlike the initial enrollment request, completion never accepts a
    requester public key from the request body. The enrollment created
    during first contact is the authority for the requester's machine
    identity.
    """

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

    nexus_peer_request_auth_service.validate_protocol(
        protocol
    )
    nexus_peer_request_auth_service.validate_algorithm(
        algorithm
    )

    normalized_method = (
        nexus_peer_request_auth_service.normalize_method(
            method
        )
    )
    normalized_path = (
        nexus_peer_request_auth_service.normalize_path(
            path
        )
    )
    normalized_nonce = (
        nexus_peer_request_auth_service.normalize_nonce(
            nonce
        )
    )

    if target_instance_id != local_instance_id:
        raise PermissionError(
            "Enrollment completion target does not match local Nexus"
        )

    if sender_instance_id == local_instance_id:
        raise PermissionError(
            "Local Nexus cannot complete enrollment with itself"
        )

    enrollment_id = _text(
        payload.get("enrollmentId")
    )
    pairing_id = _text(
        payload.get("pairingId")
    )
    capability = _text(
        payload.get("enrollmentCapability")
    )

    if not enrollment_id:
        raise PermissionError(
            "Enrollment completion enrollmentId is required"
        )

    if not pairing_id:
        raise PermissionError(
            "Enrollment completion pairingId is required"
        )

    if not capability:
        raise PermissionError(
            "Enrollment completion capability is required"
        )

    forbidden_identity_fields = (
        "remoteInstanceId",
        "publicKeyAlgorithm",
        "publicKey",
        "publicKeyFingerprint",
    )

    if any(
        _text(payload.get(field))
        for field in forbidden_identity_fields
    ):
        raise PermissionError(
            "Enrollment completion must not supply machine identity"
        )

    enrollment = (
        nexus_peer_enrollment_repository
        .get_enrollment(enrollment_id)
    )

    if enrollment is None:
        raise PermissionError(
            "Enrollment completion is invalid"
        )

    stored_local_instance_id = _text(
        enrollment.get("local_instance_id")
    )
    stored_remote_instance_id = _text(
        enrollment.get(
            "requested_remote_instance_id"
        )
    )
    stored_pairing_id = _text(
        enrollment.get("request_id")
    )
    stored_algorithm = _text(
        enrollment.get(
            "requested_public_key_algorithm"
        )
    )
    stored_public_key = _text(
        enrollment.get(
            "requested_public_key"
        )
    )
    stored_fingerprint = _text(
        enrollment.get(
            "requested_public_key_fingerprint"
        )
    )

    if stored_local_instance_id != local_instance_id:
        raise PermissionError(
            "Enrollment completion local identity mismatch"
        )

    if (
        not stored_remote_instance_id
        or stored_remote_instance_id
        != sender_instance_id
    ):
        raise PermissionError(
            "Enrollment completion sender identity mismatch"
        )

    if (
        not stored_pairing_id
        or stored_pairing_id != pairing_id
    ):
        raise PermissionError(
            "Enrollment completion pairing identity mismatch"
        )

    if (
        stored_algorithm != algorithm
        or stored_algorithm != "Ed25519"
    ):
        raise PermissionError(
            "Enrollment completion machine algorithm mismatch"
        )

    if (
        not stored_public_key
        or not stored_fingerprint
    ):
        raise PermissionError(
            "Enrollment completion stored machine identity is invalid"
        )

    try:
        raw_public_key = (
            nexus_peer_machine_identity_service
            .decode_public_key(
                stored_public_key
            )
        )

        calculated_fingerprint = (
            nexus_peer_machine_identity_service
            .public_key_fingerprint(
                raw_public_key
            )
        )
    except (TypeError, ValueError) as exc:
        raise PermissionError(
            "Enrollment completion stored machine identity is invalid"
        ) from exc

    if (
        calculated_fingerprint
        != stored_fingerprint
    ):
        raise PermissionError(
            "Enrollment completion stored fingerprint mismatch"
        )

    calculated_digest = (
        nexus_peer_request_auth_service.body_sha256(
            body
        )
    )

    if (
        supplied_digest.lower()
        != calculated_digest
    ):
        raise PermissionError(
            "Enrollment completion body digest mismatch"
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
                public_key=stored_public_key,
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
            "Enrollment completion signature is invalid"
        ) from exc

    if not verified:
        raise PermissionError(
            "Enrollment completion signature is invalid"
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
            "Enrollment completion replay detected"
        )

    return {
        "authenticated": True,
        "localInstanceId": local_instance_id,
        "remoteInstanceId": sender_instance_id,
        "enrollmentId": enrollment_id,
        "pairingId": pairing_id,
        "publicKeyFingerprint": stored_fingerprint,
    }
