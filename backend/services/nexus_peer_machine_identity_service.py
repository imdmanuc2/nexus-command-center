"""Local Ed25519 machine identity for Nexus peer authentication.

Private key material belongs only in Nexus private runtime storage.
Only public identity material may be exchanged with or persisted for peers.
"""

from __future__ import annotations

import base64
import hashlib
import os
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)


KEY_ALGORITHM = "Ed25519"
DEFAULT_PRIVATE_KEY_PATH = (
    "backend/data/private/nexus-peer-machine-ed25519.key"
)


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def private_key_path() -> Path:
    configured = _text(
        os.getenv("NEXUS_PEER_MACHINE_PRIVATE_KEY_FILE")
    )

    return Path(
        configured or DEFAULT_PRIVATE_KEY_PATH
    )


def _raw_private_key(
    private_key: Ed25519PrivateKey,
) -> bytes:
    return private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )


def _raw_public_key(
    public_key: Ed25519PublicKey,
) -> bytes:
    return public_key.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )


def encode_public_key(raw_public_key: bytes) -> str:
    if len(raw_public_key) != 32:
        raise ValueError(
            "Ed25519 public key must be 32 bytes"
        )

    return base64.urlsafe_b64encode(
        raw_public_key
    ).decode("ascii").rstrip("=")


def decode_public_key(encoded: str) -> bytes:
    value = _text(encoded)

    if not value:
        raise ValueError(
            "publicKey is required"
        )

    padding = "=" * (-len(value) % 4)

    try:
        raw = base64.urlsafe_b64decode(
            value + padding
        )
    except Exception as exc:
        raise ValueError(
            "publicKey is not valid base64url"
        ) from exc

    if len(raw) != 32:
        raise ValueError(
            "Ed25519 public key must be 32 bytes"
        )

    return raw


def public_key_fingerprint(
    raw_public_key: bytes,
) -> str:
    if len(raw_public_key) != 32:
        raise ValueError(
            "Ed25519 public key must be 32 bytes"
        )

    digest = hashlib.sha256(
        raw_public_key
    ).hexdigest()

    return f"sha256:{digest}"


def generate_private_key() -> Ed25519PrivateKey:
    """Generate an in-memory key without persisting it."""

    return Ed25519PrivateKey.generate()


def public_identity_from_private_key(
    private_key: Ed25519PrivateKey,
) -> dict[str, str]:
    raw_public = _raw_public_key(
        private_key.public_key()
    )

    return {
        "algorithm": KEY_ALGORITHM,
        "publicKey": encode_public_key(
            raw_public
        ),
        "fingerprint": public_key_fingerprint(
            raw_public
        ),
    }


def persist_private_key(
    private_key: Ed25519PrivateKey,
    *,
    path: Path | None = None,
) -> Path:
    """Persist a raw private key with owner-only permissions."""

    target = path or private_key_path()
    parent_existed = target.parent.exists()

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
        mode=0o700,
    )

    if not parent_existed:
        os.chmod(target.parent, 0o700)

    raw_private = _raw_private_key(
        private_key
    )

    if target.exists():
        raise FileExistsError(
            f"Private key already exists: {target}"
        )

    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
    )

    fd = os.open(
        target,
        flags,
        0o600,
    )

    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw_private)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            target.unlink()
        except FileNotFoundError:
            pass
        raise

    os.chmod(target, 0o600)

    return target


def load_private_key(
    *,
    path: Path | None = None,
) -> Ed25519PrivateKey:
    target = path or private_key_path()

    raw = target.read_bytes()

    if len(raw) != 32:
        raise ValueError(
            "Stored Ed25519 private key must be 32 bytes"
        )

    return Ed25519PrivateKey.from_private_bytes(
        raw
    )


def load_or_create_private_key(
    *,
    path: Path | None = None,
) -> Ed25519PrivateKey:
    target = path or private_key_path()

    if target.exists():
        return load_private_key(
            path=target
        )

    key = generate_private_key()

    try:
        persist_private_key(
            key,
            path=target,
        )
        return key
    except FileExistsError:
        # Another process won the first-start race.
        return load_private_key(
            path=target
        )


def local_public_identity(
    *,
    create: bool = False,
    path: Path | None = None,
) -> dict[str, str]:
    target = path or private_key_path()

    if create:
        key = load_or_create_private_key(
            path=target
        )
    else:
        if not target.exists():
            raise FileNotFoundError(
                f"Peer machine private key does not exist: {target}"
            )

        key = load_private_key(
            path=target
        )

    return public_identity_from_private_key(
        key
    )


def sign(
    message: bytes,
    *,
    path: Path | None = None,
) -> bytes:
    if not isinstance(message, bytes):
        raise TypeError(
            "message must be bytes"
        )

    return load_private_key(
        path=path
    ).sign(message)


def verify(
    *,
    public_key: str,
    message: bytes,
    signature: bytes,
) -> bool:
    if not isinstance(message, bytes):
        raise TypeError(
            "message must be bytes"
        )

    if not isinstance(signature, bytes):
        raise TypeError(
            "signature must be bytes"
        )

    raw_public = decode_public_key(
        public_key
    )

    key = Ed25519PublicKey.from_public_bytes(
        raw_public
    )

    try:
        key.verify(
            signature,
            message,
        )
    except InvalidSignature:
        return False

    return True
