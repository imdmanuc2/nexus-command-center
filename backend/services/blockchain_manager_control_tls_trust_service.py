"""Target-bound TLS trust for Nexus -> Blockchain Manager control.

Only public CA trust material is stored here. Private CA keys and
Blockchain Manager bearer credentials are outside this service.

The trust file is bound to one CMDB target identity and is used to
construct a strict client SSLContext with:

- certificate verification required
- hostname/IP verification enabled
- SERVER_AUTH purpose
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import ssl
from typing import Any


_TRUST_DIRECTORY = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "private"
    / "blockchain-manager-control-trust"
)

_TARGET_ID_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$"
)

_CERTIFICATE_BEGIN = (
    "-----BEGIN CERTIFICATE-----"
)

_CERTIFICATE_END = (
    "-----END CERTIFICATE-----"
)


def _text(value: Any) -> str:
    return (
        ""
        if value is None
        else str(value).strip()
    )


def _target_asset_id(
    value: Any,
) -> str:
    target = _text(
        value
    )

    if not _TARGET_ID_RE.fullmatch(
        target
    ):
        raise ValueError(
            "Invalid Blockchain Manager TLS trust target"
        )

    return target


def trust_directory() -> Path:
    return _TRUST_DIRECTORY


def trust_path(
    target_asset_id: str,
    *,
    directory: Path | None = None,
) -> Path:
    target = _target_asset_id(
        target_asset_id
    )

    root = (
        Path(directory)
        if directory is not None
        else trust_directory()
    )

    return root / (
        target + ".ca.pem"
    )


def _require_directory_security(
    directory: Path,
) -> None:
    if not directory.exists():
        raise ValueError(
            "Blockchain Manager TLS trust directory is missing"
        )

    if not directory.is_dir():
        raise ValueError(
            "Blockchain Manager TLS trust directory is invalid"
        )

    if directory.is_symlink():
        raise ValueError(
            "Blockchain Manager TLS trust directory must not be a symlink"
        )

    mode = (
        directory.stat().st_mode
        & 0o777
    )

    if mode & 0o077:
        raise ValueError(
            "Blockchain Manager TLS trust directory permissions "
            "must not grant group or other access"
        )


def _require_file_security(
    path: Path,
) -> None:
    if not path.exists():
        raise ValueError(
            "Blockchain Manager TLS trust is missing"
        )

    if not path.is_file():
        raise ValueError(
            "Blockchain Manager TLS trust file is invalid"
        )

    if path.is_symlink():
        raise ValueError(
            "Blockchain Manager TLS trust file must not be a symlink"
        )

    mode = (
        path.stat().st_mode
        & 0o777
    )

    if mode & 0o077:
        raise ValueError(
            "Blockchain Manager TLS trust file permissions "
            "must not grant group or other access"
        )


def load_ca_file(
    *,
    target_asset_id: str,
    directory: Path | None = None,
) -> Path:
    target = _target_asset_id(
        target_asset_id
    )

    root = (
        Path(directory)
        if directory is not None
        else trust_directory()
    )

    _require_directory_security(
        root
    )

    path = trust_path(
        target,
        directory=root,
    )

    _require_file_security(
        path
    )

    try:
        content = path.read_text(
            encoding="utf-8"
        )
    except OSError as exc:
        raise ValueError(
            "Blockchain Manager TLS trust file cannot be read"
        ) from exc

    if (
        _CERTIFICATE_BEGIN not in content
        or _CERTIFICATE_END not in content
    ):
        raise ValueError(
            "Blockchain Manager TLS trust file "
            "does not contain a PEM certificate"
        )

    return path


def create_ssl_context(
    *,
    target_asset_id: str,
    directory: Path | None = None,
) -> ssl.SSLContext:
    ca_file = load_ca_file(
        target_asset_id=target_asset_id,
        directory=directory,
    )

    try:
        context = ssl.create_default_context(
            purpose=ssl.Purpose.SERVER_AUTH,
            cafile=os.fspath(
                ca_file
            ),
        )
    except (
        OSError,
        ssl.SSLError,
    ) as exc:
        raise ValueError(
            "Blockchain Manager TLS trust "
            "certificate is invalid"
        ) from exc

    context.check_hostname = True
    context.verify_mode = ssl.CERT_REQUIRED

    return context
