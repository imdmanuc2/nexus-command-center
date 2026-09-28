"""Protected durable credentials for Nexus -> Blockchain Manager control.

Control credentials are encrypted at rest outside PostgreSQL and CMDB.

Encryption uses the permanent local Nexus Ed25519 machine identity as
HKDF key material. Ciphertext is authenticated and bound to both:

- the local Nexus instance identity
- the target CMDB asset identity

The plaintext bearer credential must never be projected into CMDB,
operation parameters, operation evidence, logs, or API responses.
"""

from __future__ import annotations

import base64
import json
import os
import re
import secrets
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from backend.services import nexus_instance_service
from backend.services import nexus_peer_machine_identity_service


FORMAT_VERSION = 1
NONCE_BYTES = 12
KEY_BYTES = 32

HKDF_SALT = (
    b"seymour-blockchain-manager-control-credential-v1"
)

HKDF_INFO = (
    b"blockchain-manager-control-credential-aes256gcm"
)

DEFAULT_CREDENTIAL_DIRECTORY = (
    "backend/data/private/"
    "blockchain-manager-control-credentials"
)

_TARGET_ASSET_ID_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
)


def _text(value: Any) -> str:
    return (
        ""
        if value is None
        else str(value).strip()
    )


def _target_asset_id(value: Any) -> str:
    target = _text(value)

    if not target:
        raise ValueError(
            "targetAssetId is required"
        )

    if not _TARGET_ASSET_ID_RE.fullmatch(
        target
    ):
        raise ValueError(
            "targetAssetId is invalid"
        )

    return target


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


def credential_directory() -> Path:
    configured = _text(
        os.getenv(
            "NEXUS_BLOCKCHAIN_MANAGER_CREDENTIAL_DIR"
        )
    )

    return Path(
        configured
        or DEFAULT_CREDENTIAL_DIRECTORY
    )


def credential_path(
    target_asset_id: str,
    *,
    directory: Path | None = None,
) -> Path:
    target = _target_asset_id(
        target_asset_id
    )

    parent = (
        directory
        or credential_directory()
    )

    return parent / (
        target + ".credential"
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
        or local.get("instanceId")
    )

    if not instance_id:
        raise RuntimeError(
            "Local Nexus instance identity is invalid"
        )

    return instance_id


def _machine_private_bytes() -> bytes:
    key = (
        nexus_peer_machine_identity_service
        .load_private_key()
    )

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
    target_asset_id: str,
) -> bytes:
    return (
        "blockchain-manager-control-credential-v1\n"
        f"localInstanceId={local_instance_id}\n"
        f"targetAssetId={target_asset_id}"
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


def generate_credential() -> str:
    return secrets.token_urlsafe(32)


def store_credential(
    *,
    target_asset_id: str,
    control_secret: str,
    directory: Path | None = None,
) -> Path:
    target_id = _target_asset_id(
        target_asset_id
    )

    secret = _text(
        control_secret
    )

    if not secret:
        raise ValueError(
            "controlSecret is required"
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
            "controlSecret": secret,
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
                _local_instance_id()
            ),
            target_asset_id=target_id,
        ),
    )

    document = json.dumps(
        {
            "version": FORMAT_VERSION,
            "algorithm": "AES-256-GCM",
            "keyDerivation": "HKDF-SHA256",
            "nonce": _b64encode(
                nonce
            ),
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
            "Blockchain Manager control "
            "credential already exists"
        ) from None

    try:
        with os.fdopen(
            fd,
            "wb",
        ) as handle:
            handle.write(
                document
            )
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
    target_asset_id: str,
    directory: Path | None = None,
) -> str:
    target_id = _target_asset_id(
        target_asset_id
    )

    target = credential_path(
        target_id,
        directory=directory,
    )

    mode = (
        target.stat().st_mode
        & 0o777
    )

    if mode & 0o077:
        raise PermissionError(
            "Blockchain Manager control "
            "credential permissions must not "
            "allow group or other access"
        )

    try:
        document = json.loads(
            target.read_text(
                encoding="utf-8"
            )
        )

    except Exception as exc:
        raise ValueError(
            "Blockchain Manager control "
            "credential file is invalid"
        ) from exc

    if not isinstance(
        document,
        dict,
    ):
        raise ValueError(
            "Blockchain Manager control "
            "credential file is invalid"
        )

    if (
        document.get("version")
        != FORMAT_VERSION
    ):
        raise ValueError(
            "Unsupported Blockchain Manager "
            "control credential version"
        )

    if (
        document.get("algorithm")
        != "AES-256-GCM"
    ):
        raise ValueError(
            "Unsupported Blockchain Manager "
            "control credential algorithm"
        )

    if (
        document.get("keyDerivation")
        != "HKDF-SHA256"
    ):
        raise ValueError(
            "Unsupported Blockchain Manager "
            "control credential key derivation"
        )

    nonce = _b64decode(
        document.get("nonce"),
        field="nonce",
    )

    if len(nonce) != NONCE_BYTES:
        raise ValueError(
            "Blockchain Manager control "
            "credential nonce is invalid"
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
                target_asset_id=target_id,
            ),
        )

    except Exception as exc:
        raise ValueError(
            "Blockchain Manager control "
            "credential authentication failed"
        ) from exc

    try:
        payload = json.loads(
            plaintext.decode(
                "utf-8"
            )
        )

    except Exception as exc:
        raise ValueError(
            "Blockchain Manager control "
            "credential plaintext is invalid"
        ) from exc

    if not isinstance(
        payload,
        dict,
    ):
        raise ValueError(
            "Blockchain Manager control "
            "credential plaintext is invalid"
        )

    if (
        payload.get("version")
        != FORMAT_VERSION
    ):
        raise ValueError(
            "Blockchain Manager control "
            "credential plaintext version is invalid"
        )

    secret = _text(
        payload.get(
            "controlSecret"
        )
    )

    if not secret:
        raise ValueError(
            "Blockchain Manager control "
            "credential does not contain a secret"
        )

    return secret


def delete_credential(
    *,
    target_asset_id: str,
    directory: Path | None = None,
) -> bool:
    target = credential_path(
        target_asset_id,
        directory=directory,
    )

    try:
        target.unlink()
    except FileNotFoundError:
        return False

    return True


def credential_exists(
    *,
    target_asset_id: str,
    directory: Path | None = None,
) -> bool:
    return credential_path(
        target_asset_id,
        directory=directory,
    ).is_file()
