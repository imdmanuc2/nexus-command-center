"""Signed initiator transport for Nexus enrollment requests.

This module performs only the remote enrollment-request exchange.
It does not persist outbound pairing state, store credentials, create
peers, approve enrollments, or consume enrollments.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from backend.services import nexus_instance_service
from backend.services import nexus_peer_machine_identity_service
from backend.services import nexus_peer_pairing_service
from backend.services import nexus_peer_request_auth_service


ENROLLMENT_REQUEST_PATH = "/api/nexus/enrollment/request"
DEFAULT_TIMEOUT_SECONDS = 10.0
MAX_TIMEOUT_SECONDS = 60.0
MAX_RESPONSE_BODY_BYTES = 64 * 1024


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _local_instance() -> dict[str, str]:
    local = nexus_instance_service.get_local_instance()

    if not local:
        raise RuntimeError(
            "Local Nexus instance is not registered"
        )

    instance_id = _text(
        local.get("instance_id")
        or local.get("instanceId")
    )

    name = _text(
        local.get("name")
        or local.get("instance_name")
        or local.get("instanceName")
    )

    hostname = _text(
        local.get("hostname")
    )

    if not instance_id:
        raise RuntimeError(
            "Local Nexus instance ID is missing"
        )

    if not name:
        raise RuntimeError(
            "Local Nexus instance name is missing"
        )

    if not hostname:
        raise RuntimeError(
            "Local Nexus instance hostname is missing"
        )

    return {
        "instanceId": instance_id,
        "name": name,
        "hostname": hostname,
    }


def enrollment_request_url(
    peer_base_url: str,
) -> str:
    base = (
        nexus_peer_pairing_service
        .normalize_peer_base_url(
            peer_base_url
        )
    )

    url = (
        base.rstrip("/")
        + ENROLLMENT_REQUEST_PATH
    )

    parsed = urlparse(url)

    if (
        parsed.path != ENROLLMENT_REQUEST_PATH
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "Enrollment request URL is not canonical"
        )

    return url


def _timeout_value(
    timeout: Any,
) -> float:
    if isinstance(timeout, bool):
        raise ValueError(
            "timeout must be a positive number"
        )

    try:
        value = float(timeout)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "timeout must be a positive number"
        ) from exc

    if (
        value <= 0
        or value > MAX_TIMEOUT_SECONDS
    ):
        raise ValueError(
            "timeout must be greater than 0 "
            "and no more than 60 seconds"
        )

    return value


def _encode_request_body(
    payload: dict[str, Any],
) -> bytes:
    return json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _decode_response(
    raw: bytes,
) -> dict[str, Any]:
    if not isinstance(raw, bytes):
        raise RuntimeError(
            "Nexus enrollment response body must be bytes"
        )

    if len(raw) > MAX_RESPONSE_BODY_BYTES:
        raise RuntimeError(
            "Nexus enrollment response body is too large"
        )

    try:
        payload = json.loads(
            raw.decode("utf-8")
        )
    except Exception as exc:
        raise RuntimeError(
            "Nexus enrollment response is invalid JSON"
        ) from exc

    if not isinstance(payload, dict):
        raise RuntimeError(
            "Nexus enrollment response must be an object"
        )

    return payload


def build_signed_enrollment_request(
    *,
    remote_instance_id: str,
    peer_base_url: str,
    local_peer_base_url: str,
    timestamp: datetime | str | None = None,
    nonce: str | None = None,
) -> dict[str, Any]:
    """Build one authenticated enrollment request.

    No network request or persistent mutation occurs here.
    """

    remote_id = _text(
        remote_instance_id
    )

    if not remote_id:
        raise ValueError(
            "remoteInstanceId is required"
        )

    local = _local_instance()

    if remote_id == local["instanceId"]:
        raise ValueError(
            "Cannot request pairing with local Nexus"
        )

    remote_url = enrollment_request_url(
        peer_base_url
    )

    local_base_url = (
        nexus_peer_pairing_service
        .normalize_peer_base_url(
            local_peer_base_url
        )
    )

    machine = (
        nexus_peer_machine_identity_service
        .local_public_identity()
    )

    algorithm = _text(
        machine.get("algorithm")
    )
    public_key = _text(
        machine.get("publicKey")
        or machine.get("public_key")
    )
    fingerprint = _text(
        machine.get("fingerprint")
    )

    if (
        algorithm != "Ed25519"
        or not public_key
        or not fingerprint
    ):
        raise RuntimeError(
            "Local Nexus machine identity is invalid"
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

    if expected_fingerprint != fingerprint:
        raise RuntimeError(
            "Local Nexus machine identity fingerprint mismatch"
        )

    payload = {
        "remoteInstanceId": local["instanceId"],
        "remoteName": local["name"],
        "remoteHostname": local["hostname"],
        "peerBaseUrl": local_base_url,
        "publicKeyAlgorithm": algorithm,
        "publicKey": public_key,
        "publicKeyFingerprint": fingerprint,
    }

    body = _encode_request_body(
        payload
    )

    timestamp_value = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        if timestamp is None
        else timestamp
    )

    signed = (
        nexus_peer_request_auth_service
        .sign_request(
            method="POST",
            path=ENROLLMENT_REQUEST_PATH,
            sender_instance_id=local["instanceId"],
            target_instance_id=remote_id,
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
            "Outbound enrollment auth header contract mismatch"
        )

    return {
        "method": "POST",
        "url": remote_url,
        "path": ENROLLMENT_REQUEST_PATH,
        "headers": headers,
        "body": body,
        "payload": payload,
        "localInstanceId": local["instanceId"],
        "remoteInstanceId": remote_id,
    }


def request_remote_enrollment(
    *,
    remote_instance_id: str,
    peer_base_url: str,
    local_peer_base_url: str,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    timestamp: datetime | str | None = None,
    nonce: str | None = None,
    opener: Callable[..., Any] = urlopen,
) -> dict[str, Any]:
    """Send one signed remote enrollment request.

    The returned enrollment secret is intentionally ephemeral. Callers
    are responsible for immediately placing it into protected credential
    storage before advancing durable outbound pairing state.
    """

    timeout_value = _timeout_value(
        timeout
    )

    outbound = build_signed_enrollment_request(
        remote_instance_id=remote_instance_id,
        peer_base_url=peer_base_url,
        local_peer_base_url=local_peer_base_url,
        timestamp=timestamp,
        nonce=nonce,
    )

    request = Request(
        outbound["url"],
        data=outbound["body"],
        headers={
            **outbound["headers"],
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with opener(
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
                "Nexus enrollment error response is too large"
            ) from exc

        raise RuntimeError(
            f"Nexus enrollment request returned HTTP {exc.code}"
        ) from exc

    except URLError as exc:
        raise RuntimeError(
            "Nexus enrollment transport failed"
        ) from exc

    except TimeoutError as exc:
        raise RuntimeError(
            "Nexus enrollment transport timed out"
        ) from exc

    if status != 201:
        raise RuntimeError(
            f"Nexus enrollment request returned HTTP {status}"
        )

    payload = _decode_response(
        raw
    )

    if payload.get("status") != "ok":
        raise RuntimeError(
            "Nexus enrollment request returned unsuccessful status"
        )

    enrollment = payload.get(
        "enrollment"
    )

    if not isinstance(enrollment, dict):
        raise RuntimeError(
            "Nexus enrollment response is missing enrollment"
        )

    enrollment_id = _text(
        enrollment.get(
            "enrollmentId"
        )
    )

    enrollment_status = _text(
        enrollment.get(
            "status"
        )
    )

    requested_remote = _text(
        enrollment.get(
            "requestedRemoteInstanceId"
        )
    )

    remote_local_instance = _text(
        enrollment.get(
            "localInstanceId"
        )
    )

    enrollment_secret = _text(
        payload.get(
            "enrollmentSecret"
        )
    )

    if not enrollment_id:
        raise RuntimeError(
            "Nexus enrollment response is missing enrollmentId"
        )

    if enrollment_status != "pending":
        raise RuntimeError(
            "Nexus enrollment response is not pending"
        )

    if (
        requested_remote
        != outbound["localInstanceId"]
    ):
        raise RuntimeError(
            "Nexus enrollment response targets the wrong requester"
        )

    if (
        remote_local_instance
        != outbound["remoteInstanceId"]
    ):
        raise RuntimeError(
            "Nexus enrollment response came from the wrong Nexus"
        )

    if not enrollment_secret:
        raise RuntimeError(
            "Nexus enrollment response is missing credential"
        )

    return {
        "status": "ok",
        "enrollmentId": enrollment_id,
        "enrollmentStatus": enrollment_status,
        "expiresAt": enrollment.get(
            "expiresAt"
        ),
        "enrollmentSecret": enrollment_secret,
    }
