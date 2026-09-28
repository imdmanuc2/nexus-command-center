from __future__ import annotations

import json
import time
from dataclasses import dataclass
from typing import Callable

from backend.services.blockchain_target_platform import UMBREL_TARGET_PROFILE
from backend.transports.models import (
    TransportResult,
    TransportTarget,
)
from backend.transports.ssh_transport import SshTransport


REMOTE_STAGE_ROOT = UMBREL_TARGET_PROFILE.staging_root
BOOTSTRAP_DIR = (
    REMOTE_STAGE_ROOT + "/seymour-bootstrap"
)
BOOTSTRAP_PROGRAM = (
    BOOTSTRAP_DIR + "/bootstrap.py"
)

EXPECTED_BOOTSTRAP_MEMBERS = (
    "seymour-bootstrap/bootstrap.py",
    "seymour-bootstrap/runtime_installer.py",
)


class BootstrapInvocationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BootstrapInvocationRequest:
    bootstrap_artifact_id: str
    bootstrap_sha256: str
    runtime_artifact_id: str
    runtime_sha256: str
    payload_manifest_sha256: str
    runtime_version: str
    source_revision: str


@dataclass(frozen=True, slots=True)
class BootstrapInvocationResult:
    bootstrap_sha256: str
    runtime_sha256: str
    payload_manifest_sha256: str
    runtime_version: str
    source_revision: str
    duration_ms: int
    exit_code: int
    host_key_verified: bool
    result: dict


def _required(value: str, name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise BootstrapInvocationError(
            f"{name} is required"
        )
    return normalized


def _sha256(value: str, name: str) -> str:
    normalized = _required(value, name).lower()

    if (
        len(normalized) != 64
        or any(
            character not in "0123456789abcdef"
            for character in normalized
        )
    ):
        raise BootstrapInvocationError(
            f"{name} is invalid"
        )

    return normalized


def _artifact_id(value: str, name: str) -> str:
    normalized = _required(value, name)

    if (
        "/" in normalized
        or "\\" in normalized
        or normalized in {".", ".."}
        or ".." in normalized
    ):
        raise BootstrapInvocationError(
            f"{name} is invalid"
        )

    allowed = set(
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        "0123456789_.-"
    )

    if (
        len(normalized) > 128
        or normalized[0] not in allowed
        or any(ch not in allowed for ch in normalized)
    ):
        raise BootstrapInvocationError(
            f"{name} is invalid"
        )

    return normalized


def _remote_artifact_path(
    artifact_id: str,
) -> str:
    return f"{REMOTE_STAGE_ROOT}/{artifact_id}"


class SshBootstrapInvocationTransport:
    """
    Narrow SSH primitive for one reviewed operation:

      1. verify both staged artifact hashes;
      2. inspect the bootstrap archive member list;
      3. reset a fixed bootstrap extraction directory;
      4. extract the reviewed bootstrap archive;
      5. invoke the fixed bootstrap.py program with reviewed metadata.

    Callers cannot supply remote paths, extraction paths, commands,
    shells, arbitrary argv, or transport selection.
    """

    def __init__(
        self,
        *,
        transport: SshTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._transport = transport or SshTransport()
        self._clock = clock

    def _execute(
        self,
        *,
        target: TransportTarget,
        argv: list[str],
        timeout_seconds: int,
    ) -> TransportResult:
        result = self._transport.execute(
            target=target,
            argv=argv,
            timeout_seconds=timeout_seconds,
        )

        if result.exit_code != 0:
            raise BootstrapInvocationError(
                "reviewed bootstrap remote operation failed"
            )

        if not result.host_key_verified:
            raise BootstrapInvocationError(
                "reviewed bootstrap host key was not verified"
            )

        return result

    def invoke(
        self,
        *,
        target: TransportTarget,
        request: BootstrapInvocationRequest,
        timeout_seconds: int,
    ) -> BootstrapInvocationResult:
        if target.transport != "ssh":
            raise BootstrapInvocationError(
                "bootstrap invocation requires SSH target"
            )

        if timeout_seconds <= 0:
            raise BootstrapInvocationError(
                "bootstrap invocation timeout must be positive"
            )

        bootstrap_id = _artifact_id(
            request.bootstrap_artifact_id,
            "bootstrap artifact ID",
        )
        runtime_id = _artifact_id(
            request.runtime_artifact_id,
            "runtime artifact ID",
        )

        bootstrap_sha = _sha256(
            request.bootstrap_sha256,
            "bootstrap SHA-256",
        )
        runtime_sha = _sha256(
            request.runtime_sha256,
            "runtime SHA-256",
        )
        payload_sha = _sha256(
            request.payload_manifest_sha256,
            "payload manifest SHA-256",
        )

        runtime_version = _required(
            request.runtime_version,
            "runtime version",
        )
        source_revision = _required(
            request.source_revision,
            "source revision",
        )

        bootstrap_archive = _remote_artifact_path(
            bootstrap_id
        )
        runtime_archive = _remote_artifact_path(
            runtime_id
        )

        started = self._clock()

        bootstrap_hash_result = self._execute(
            target=target,
            argv=[
                "/usr/bin/sha256sum",
                "--",
                bootstrap_archive,
            ],
            timeout_seconds=timeout_seconds,
        )

        bootstrap_hash_actual = (
            bootstrap_hash_result.stdout
            .strip()
            .split()[0]
            .lower()
            if bootstrap_hash_result.stdout.strip()
            else ""
        )

        if bootstrap_hash_actual != bootstrap_sha:
            raise BootstrapInvocationError(
                "staged bootstrap SHA-256 mismatch"
            )

        runtime_hash_result = self._execute(
            target=target,
            argv=[
                "/usr/bin/sha256sum",
                "--",
                runtime_archive,
            ],
            timeout_seconds=timeout_seconds,
        )

        runtime_hash_actual = (
            runtime_hash_result.stdout
            .strip()
            .split()[0]
            .lower()
            if runtime_hash_result.stdout.strip()
            else ""
        )

        if runtime_hash_actual != runtime_sha:
            raise BootstrapInvocationError(
                "staged runtime SHA-256 mismatch"
            )

        listing_result = self._execute(
            target=target,
            argv=[
                "/usr/bin/tar",
                "-tzf",
                bootstrap_archive,
            ],
            timeout_seconds=timeout_seconds,
        )

        members = tuple(
            line.strip()
            for line in listing_result.stdout.splitlines()
            if line.strip()
        )

        if members != EXPECTED_BOOTSTRAP_MEMBERS:
            raise BootstrapInvocationError(
                "bootstrap archive member contract mismatch"
            )

        self._execute(
            target=target,
            argv=[
                "/usr/bin/rm",
                "-rf",
                "--",
                BOOTSTRAP_DIR,
            ],
            timeout_seconds=timeout_seconds,
        )

        self._execute(
            target=target,
            argv=[
                "/usr/bin/tar",
                "-xzf",
                bootstrap_archive,
                "-C",
                REMOTE_STAGE_ROOT,
            ],
            timeout_seconds=timeout_seconds,
        )

        invocation_result = self._execute(
            target=target,
            argv=[
                "/usr/bin/python3",
                BOOTSTRAP_PROGRAM,
                "--archive",
                runtime_archive,
                "--archive-sha256",
                runtime_sha,
                "--payload-manifest-sha256",
                payload_sha,
                "--runtime-version",
                runtime_version,
                "--source-revision",
                source_revision,
            ],
            timeout_seconds=timeout_seconds,
        )

        try:
            payload = json.loads(
                invocation_result.stdout.strip()
            )
        except Exception as exc:
            raise BootstrapInvocationError(
                "bootstrap returned invalid JSON"
            ) from exc

        if not isinstance(payload, dict):
            raise BootstrapInvocationError(
                "bootstrap returned invalid result"
            )

        if payload.get("success") is not True:
            raise BootstrapInvocationError(
                "bootstrap reported failure"
            )

        if payload.get("archiveSha256") != runtime_sha:
            raise BootstrapInvocationError(
                "bootstrap runtime SHA evidence mismatch"
            )

        if (
            payload.get("payloadManifestSha256")
            != payload_sha
        ):
            raise BootstrapInvocationError(
                "bootstrap payload manifest evidence mismatch"
            )

        if payload.get("runtimeVersion") != runtime_version:
            raise BootstrapInvocationError(
                "bootstrap runtime version evidence mismatch"
            )

        if payload.get("sourceRevision") != source_revision:
            raise BootstrapInvocationError(
                "bootstrap source revision evidence mismatch"
            )

        duration_ms = max(
            0,
            int((self._clock() - started) * 1000),
        )

        return BootstrapInvocationResult(
            bootstrap_sha256=bootstrap_sha,
            runtime_sha256=runtime_sha,
            payload_manifest_sha256=payload_sha,
            runtime_version=runtime_version,
            source_revision=source_revision,
            duration_ms=duration_ms,
            exit_code=invocation_result.exit_code,
            host_key_verified=True,
            result=payload,
        )
