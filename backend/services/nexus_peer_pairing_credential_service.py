"""Protected temporary credentials for outbound Nexus pairing.

Enrollment credentials are encrypted at rest outside PostgreSQL.

The encryption key is derived from the permanent local Nexus Ed25519
machine private key using HKDF-SHA256. The machine private key itself
is never copied into the credential file.

Credential ciphertext is bound to the local Nexus instance and pairing
identifier using AES-GCM associated data.
"""

from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import (
    AESGCM,
)
from cryptography.hazmat.primitives.kdf.hkdf import (
    HKDF,
)

from backend.services import (
    nexus_instance_service,
)
from backend.services import (
    nexus_peer_machine_identity_service,
)


FORMAT_VERSION = 1
NONCE_BYTES = 12
KEY_BYTES = 32

HKDF_SALT = (
    b"seymour-nexus-peer-pairing-credential-v1"
)

HKDF_INFO = (
    b"nexus-peer-pairing-credential-aes256gcm"
)

DEFAULT_CREDENTIAL_DIRECTORY = (
    "backend/data/private/"
    "nexus-peer-pairing-credentials"
)

_PAIRING_ID_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$"
)


def _text(value: Any) -> str:
    return (
        ""
        if value is None
        else str(value).strip()
    )


def _b64encode(value: bytes) -> str:
    return (
        base64.urlsafe_b64encode(value)
        .decode("ascii")
        .rstrip("=")
    )


def _b64decode(
    value: Any,
    *,
    field: str,
) -> bytes:
    encoded = _text(value)

    if not encoded:
        raise ValueError(
            f"{field} is required"
        )

    padding = "=" * (
        -len(encoded) % 4
    )

    try:
        return base64.b64decode(
            encoded + padding,
            altchars=b"-_",
            validate=True,
        )
    except Exception as exc:
        raise ValueError(
            f"{field} is invalid"
        ) from exc


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
        or local.get("instanceId")
    )

    if not instance_id:
        raise RuntimeError(
            "Local Nexus instance identity is invalid"
        )

    return instance_id


def credential_directory() -> Path:
    configured = _text(
        os.getenv(
            "NEXUS_PEER_PAIRING_CREDENTIAL_DIR"
        )
    )

    return Path(
        configured
        or DEFAULT_CREDENTIAL_DIRECTORY
    )


def _pairing_id(
    value: Any,
) -> str:
    pairing_id = _text(value)

    if not pairing_id:
        raise ValueError(
            "pairingId is required"
        )

    if not _PAIRING_ID_RE.fullmatch(
        pairing_id
    ):
        raise ValueError(
            "pairingId is invalid"
        )

    return pairing_id


def credential_path(
    pairing_id: str,
    *,
    directory: Path | None = None,
) -> Path:
    target_id = _pairing_id(
        pairing_id
    )

    parent = (
        directory
        or credential_directory()
    )

    return parent / (
        target_id + ".credential"
    )


def _machine_private_bytes() -> bytes:
    key = (
        nexus_peer_machine_identity_service
        .load_private_key()
    )

    # Keep serialization details centralized in the
    # machine identity service's persisted raw key.
    path = (
        nexus_peer_machine_identity_service
        .private_key_path()
    )

    raw = path.read_bytes()

    if len(raw) != 32:
        raise ValueError(
            "Stored Nexus machine private key "
            "must be 32 bytes"
        )

    # Ensure the persisted bytes are loadable before
    # using them as key-derivation input.
    del key

    return raw


def _encryption_key() -> bytes:
    return HKDF(
        algorithm=hashes.SHA256(),
        length=KEY_BYTES,
        salt=HKDF_SALT,
        info=HKDF_INFO,
    ).derive(
        _machine_private_bytes()
    )


def _associated_data(
    *,
    local_instance_id: str,
    pairing_id: str,
) -> bytes:
    return (
        "nexus-peer-pairing-credential-v1\n"
        f"localInstanceId={local_instance_id}\n"
        f"pairingId={pairing_id}"
    ).encode("utf-8")


def _secure_directory(
    directory: Path,
) -> None:
    if directory.exists():
        if not directory.is_dir():
            raise RuntimeError(
                "Credential path is not a directory"
            )

        mode = (
            directory.stat().st_mode
            & 0o777
        )

        if mode & 0o077:
            raise PermissionError(
                "Credential directory permissions "
                "must not allow group or other access"
            )

        return

    directory.mkdir(
        parents=True,
        mode=0o700,
    )

    os.chmod(
        directory,
        0o700,
    )


def store_credential(
    *,
    pairing_id: str,
    enrollment_secret: str,
    directory: Path | None = None,
) -> Path:
    target_id = _pairing_id(
        pairing_id
    )

    secret = _text(
        enrollment_secret
    )

    if not secret:
        raise ValueError(
            "enrollmentSecret is required"
        )

    local_instance_id = (
        _local_instance_id()
    )

    parent = (
        directory
        or credential_directory()
    )

    _secure_directory(
        parent
    )

    target = credential_path(
        target_id,
        directory=parent,
    )

    nonce = os.urandom(
        NONCE_BYTES
    )

    plaintext = json.dumps(
        {
            "version": FORMAT_VERSION,
            "enrollmentSecret": secret,
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    ciphertext = AESGCM(
        _encryption_key()
    ).encrypt(
        nonce,
        plaintext,
        _associated_data(
            local_instance_id=(
                local_instance_id
            ),
            pairing_id=target_id,
        ),
    )

    document = json.dumps(
        {
            "version": FORMAT_VERSION,
            "algorithm": "AES-256-GCM",
            "keyDerivation": "HKDF-SHA256",
            "nonce": _b64encode(nonce),
            "ciphertext": _b64encode(
                ciphertext
            ),
        },
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
    )

    try:
        fd = os.open(
            target,
            flags,
            0o600,
        )
    except FileExistsError:
        raise FileExistsError(
            "Pairing credential already exists"
        ) from None

    try:
        with os.fdopen(
            fd,
            "wb",
        ) as handle:
            handle.write(document)
            handle.flush()
            os.fsync(
                handle.fileno()
            )
    except Exception:
        try:
            target.unlink()
        except FileNotFoundError:
            pass
        raise

    os.chmod(
        target,
        0o600,
    )

    return target


def load_credential(
    *,
    pairing_id: str,
    directory: Path | None = None,
) -> str:
    target_id = _pairing_id(
        pairing_id
    )

    parent = (
        directory
        or credential_directory()
    )

    target = credential_path(
        target_id,
        directory=parent,
    )

    mode = (
        target.stat().st_mode
        & 0o777
    )

    if mode & 0o077:
        raise PermissionError(
            "Pairing credential permissions "
            "must not allow group or other access"
        )

    try:
        document = json.loads(
            target.read_text(
                encoding="utf-8"
            )
        )
    except Exception as exc:
        raise ValueError(
            "Pairing credential file is invalid"
        ) from exc

    if not isinstance(
        document,
        dict,
    ):
        raise ValueError(
            "Pairing credential file is invalid"
        )

    if document.get("version") != FORMAT_VERSION:
        raise ValueError(
            "Unsupported pairing credential version"
        )

    if (
        document.get("algorithm")
        != "AES-256-GCM"
    ):
        raise ValueError(
            "Unsupported pairing credential algorithm"
        )

    if (
        document.get("keyDerivation")
        != "HKDF-SHA256"
    ):
        raise ValueError(
            "Unsupported pairing credential key derivation"
        )

    nonce = _b64decode(
        document.get("nonce"),
        field="nonce",
    )

    if len(nonce) != NONCE_BYTES:
        raise ValueError(
            "Pairing credential nonce is invalid"
        )

    ciphertext = _b64decode(
        document.get("ciphertext"),
        field="ciphertext",
    )

    try:
        plaintext = AESGCM(
            _encryption_key()
        ).decrypt(
            nonce,
            ciphertext,
            _associated_data(
                local_instance_id=(
                    _local_instance_id()
                ),
                pairing_id=target_id,
            ),
        )
    except Exception as exc:
        raise ValueError(
            "Pairing credential authentication failed"
        ) from exc

    try:
        payload = json.loads(
            plaintext.decode("utf-8")
        )
    except Exception as exc:
        raise ValueError(
            "Pairing credential plaintext is invalid"
        ) from exc

    if not isinstance(
        payload,
        dict,
    ):
        raise ValueError(
            "Pairing credential plaintext is invalid"
        )

    if payload.get("version") != FORMAT_VERSION:
        raise ValueError(
            "Pairing credential plaintext version is invalid"
        )

    secret = _text(
        payload.get(
            "enrollmentSecret"
        )
    )

    if not secret:
        raise ValueError(
            "Pairing credential does not contain a secret"
        )

    return secret


def delete_credential(
    *,
    pairing_id: str,
    directory: Path | None = None,
) -> bool:
    target = credential_path(
        pairing_id,
        directory=directory,
    )

    try:
        target.unlink()
    except FileNotFoundError:
        return False

    return True


def credential_exists(
    *,
    pairing_id: str,
    directory: Path | None = None,
) -> bool:
    return credential_path(
        pairing_id,
        directory=directory,
    ).is_file()
