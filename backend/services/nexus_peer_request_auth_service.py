"""Canonical Ed25519 authentication contract for Nexus peer requests.

This module defines the deterministic bytes signed by Nexus peers.
It deliberately does not perform peer lookup or replay persistence.
Those responsibilities belong to the verified-peer authentication layer.
"""

from __future__ import annotations

import base64
import hashlib
import re
import secrets
from datetime import datetime, timezone
from typing import Any

from backend.services import nexus_peer_machine_identity_service


AUTH_PROTOCOL = "nexus-peer-auth-v1"
SIGNATURE_ALGORITHM = "Ed25519"
NONCE_BYTES = 32
MAX_CLOCK_SKEW_SECONDS = 120

SIGNED_FIELDS = (
    "protocol",
    "algorithm",
    "method",
    "path",
    "senderInstanceId",
    "targetInstanceId",
    "timestamp",
    "nonce",
    "bodySha256",
)

HEADER_PROTOCOL = "X-Nexus-Peer-Protocol"
HEADER_ALGORITHM = "X-Nexus-Peer-Algorithm"
HEADER_SENDER = "X-Nexus-Peer-Sender"
HEADER_TARGET = "X-Nexus-Peer-Target"
HEADER_TIMESTAMP = "X-Nexus-Peer-Timestamp"
HEADER_NONCE = "X-Nexus-Peer-Nonce"
HEADER_BODY_SHA256 = "X-Nexus-Peer-Body-SHA256"
HEADER_SIGNATURE = "X-Nexus-Peer-Signature"

AUTH_HEADERS = (
    HEADER_PROTOCOL,
    HEADER_ALGORITHM,
    HEADER_SENDER,
    HEADER_TARGET,
    HEADER_TIMESTAMP,
    HEADER_NONCE,
    HEADER_BODY_SHA256,
    HEADER_SIGNATURE,
)

_HTTP_TOKEN = re.compile(
    r"^[!#$%&'*+.^_`|~0-9A-Za-z-]+$"
)

_CANONICAL_TIMESTAMP = re.compile(
    r"^\d{4}-\d{2}-\d{2}T"
    r"\d{2}:\d{2}:\d{2}Z$"
)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _required_text(
    value: Any,
    *,
    field: str,
) -> str:
    result = _text(value)

    if not result:
        raise ValueError(
            f"{field} is required"
        )

    return result


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(
        value
    ).decode("ascii").rstrip("=")


def _base64url_decode(
    value: str,
    *,
    field: str,
) -> bytes:
    encoded = _required_text(
        value,
        field=field,
    )

    padding = "=" * (-len(encoded) % 4)

    try:
        return base64.b64decode(
            encoded + padding,
            altchars=b"-_",
            validate=True,
        )
    except Exception as exc:
        raise ValueError(
            f"{field} is not valid base64url"
        ) from exc


def generate_nonce() -> str:
    """Generate a canonical 256-bit base64url nonce."""

    return _base64url_encode(
        secrets.token_bytes(NONCE_BYTES)
    )


def normalize_nonce(nonce: Any) -> str:
    value = _required_text(
        nonce,
        field="nonce",
    )

    raw = _base64url_decode(
        value,
        field="nonce",
    )

    if len(raw) != NONCE_BYTES:
        raise ValueError(
            f"nonce must encode exactly {NONCE_BYTES} bytes"
        )

    canonical = _base64url_encode(raw)

    if value != canonical:
        raise ValueError(
            "nonce must use canonical base64url encoding"
        )

    return canonical


def validate_protocol(protocol: Any) -> str:
    value = _required_text(
        protocol,
        field="protocol",
    )

    if value != AUTH_PROTOCOL:
        raise ValueError(
            "Unsupported peer authentication protocol"
        )

    return value


def validate_algorithm(algorithm: Any) -> str:
    value = _required_text(
        algorithm,
        field="algorithm",
    )

    if value != SIGNATURE_ALGORITHM:
        raise ValueError(
            "Unsupported peer authentication algorithm"
        )

    return value


def normalize_method(method: Any) -> str:
    value = _required_text(
        method,
        field="method",
    )

    if not _HTTP_TOKEN.fullmatch(value):
        raise ValueError(
            "method must be a valid HTTP token"
        )

    return value.upper()


def normalize_path(path: Any) -> str:
    value = _required_text(
        path,
        field="path",
    )

    if not value.startswith("/"):
        raise ValueError(
            "path must begin with /"
        )

    if "\r" in value or "\n" in value:
        raise ValueError(
            "path must not contain line breaks"
        )

    if "?" in value or "#" in value:
        raise ValueError(
            "signed path must not contain query or fragment"
        )

    return value


def normalize_timestamp(timestamp: Any) -> str:
    if isinstance(timestamp, datetime):
        if timestamp.tzinfo is None:
            raise ValueError(
                "timestamp must include timezone"
            )

        value = timestamp.astimezone(
            timezone.utc
        )

        if value.microsecond:
            raise ValueError(
                "timestamp must use whole seconds"
            )

        return value.strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )

    value = _required_text(
        timestamp,
        field="timestamp",
    )

    if not _CANONICAL_TIMESTAMP.fullmatch(value):
        raise ValueError(
            "timestamp must use canonical UTC format "
            "YYYY-MM-DDTHH:MM:SSZ"
        )

    try:
        datetime.strptime(
            value,
            "%Y-%m-%dT%H:%M:%SZ",
        )
    except ValueError as exc:
        raise ValueError(
            "timestamp is invalid"
        ) from exc

    return value


def timestamp_datetime(timestamp: Any) -> datetime:
    normalized = normalize_timestamp(
        timestamp
    )

    return datetime.strptime(
        normalized,
        "%Y-%m-%dT%H:%M:%SZ",
    ).replace(
        tzinfo=timezone.utc
    )


def validate_timestamp_freshness(
    timestamp: Any,
    *,
    now: datetime | None = None,
    max_clock_skew_seconds: int = MAX_CLOCK_SKEW_SECONDS,
) -> str:
    if (
        not isinstance(max_clock_skew_seconds, int)
        or isinstance(max_clock_skew_seconds, bool)
        or max_clock_skew_seconds < 0
    ):
        raise ValueError(
            "max_clock_skew_seconds must be a non-negative integer"
        )

    parsed = timestamp_datetime(
        timestamp
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

    difference = abs(
        (current - parsed).total_seconds()
    )

    if difference > max_clock_skew_seconds:
        raise PermissionError(
            "Peer authentication timestamp is outside "
            "the allowed clock-skew window"
        )

    return normalize_timestamp(
        timestamp
    )


def body_sha256(body: bytes) -> str:
    if not isinstance(body, bytes):
        raise TypeError(
            "body must be bytes"
        )

    return hashlib.sha256(
        body
    ).hexdigest()


def canonical_request(
    *,
    protocol: Any = AUTH_PROTOCOL,
    algorithm: Any = SIGNATURE_ALGORITHM,
    method: Any,
    path: Any,
    sender_instance_id: Any,
    target_instance_id: Any,
    timestamp: Any,
    nonce: Any,
    body_sha256_value: Any,
) -> bytes:
    values = {
        "protocol": validate_protocol(
            protocol
        ),
        "algorithm": validate_algorithm(
            algorithm
        ),
        "method": normalize_method(
            method
        ),
        "path": normalize_path(
            path
        ),
        "senderInstanceId": _required_text(
            sender_instance_id,
            field="senderInstanceId",
        ),
        "targetInstanceId": _required_text(
            target_instance_id,
            field="targetInstanceId",
        ),
        "timestamp": normalize_timestamp(
            timestamp
        ),
        "nonce": normalize_nonce(
            nonce
        ),
        "bodySha256": _required_text(
            body_sha256_value,
            field="bodySha256",
        ).lower(),
    }

    digest = values["bodySha256"]

    if (
        len(digest) != 64
        or any(
            character not in "0123456789abcdef"
            for character in digest
        )
    ):
        raise ValueError(
            "bodySha256 must be a SHA-256 hex digest"
        )

    lines = [
        f"{field}:{values[field]}"
        for field in SIGNED_FIELDS
    ]

    return (
        "\n".join(lines) + "\n"
    ).encode("utf-8")


def sign_request(
    *,
    method: Any,
    path: Any,
    sender_instance_id: Any,
    target_instance_id: Any,
    timestamp: Any,
    body: bytes,
    nonce: Any | None = None,
) -> dict[str, str]:
    digest = body_sha256(body)

    nonce_value = (
        generate_nonce()
        if nonce is None
        else normalize_nonce(nonce)
    )

    message = canonical_request(
        protocol=AUTH_PROTOCOL,
        algorithm=SIGNATURE_ALGORITHM,
        method=method,
        path=path,
        sender_instance_id=sender_instance_id,
        target_instance_id=target_instance_id,
        timestamp=timestamp,
        nonce=nonce_value,
        body_sha256_value=digest,
    )

    signature = (
        nexus_peer_machine_identity_service
        .sign(message)
    )

    return {
        "protocol": AUTH_PROTOCOL,
        "algorithm": SIGNATURE_ALGORITHM,
        "senderInstanceId": _required_text(
            sender_instance_id,
            field="senderInstanceId",
        ),
        "targetInstanceId": _required_text(
            target_instance_id,
            field="targetInstanceId",
        ),
        "timestamp": normalize_timestamp(
            timestamp
        ),
        "nonce": nonce_value,
        "bodySha256": digest,
        "signature": _base64url_encode(
            signature
        ),
    }


def verify_signature(
    *,
    public_key: str,
    protocol: Any = AUTH_PROTOCOL,
    algorithm: Any = SIGNATURE_ALGORITHM,
    method: Any,
    path: Any,
    sender_instance_id: Any,
    target_instance_id: Any,
    timestamp: Any,
    nonce: Any,
    body_sha256_value: Any,
    signature: str,
) -> bool:
    message = canonical_request(
        protocol=protocol,
        algorithm=algorithm,
        method=method,
        path=path,
        sender_instance_id=sender_instance_id,
        target_instance_id=target_instance_id,
        timestamp=timestamp,
        nonce=nonce,
        body_sha256_value=body_sha256_value,
    )

    raw_signature = _base64url_decode(
        signature,
        field="signature",
    )

    if len(raw_signature) != 64:
        raise ValueError(
            "Ed25519 signature must be 64 bytes"
        )

    return (
        nexus_peer_machine_identity_service
        .verify(
            public_key=public_key,
            message=message,
            signature=raw_signature,
        )
    )
