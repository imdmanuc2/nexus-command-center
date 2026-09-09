from __future__ import annotations

import hashlib
import os
import re
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path

from backend.transports.models import TransportTarget
from backend.transports.ssh_transport import SshTransport


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ARTIFACT_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")

REMOTE_STAGE_ROOT = "/home/umbrel/.seymour-artifacts"


@dataclass(frozen=True, slots=True)
class ArtifactTransferRequest:
    artifact_id: str
    source: Path
    expected_sha256: str


@dataclass(frozen=True, slots=True)
class ArtifactTransferResult:
    artifact_id: str
    remote_path: str
    sha256: str
    duration_ms: int
    host_key_verified: bool


class ArtifactTransferError(RuntimeError):
    pass


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)

    return digest.hexdigest()


class SshArtifactTransport:
    """Transfer one reviewed file into a Nexus-owned target staging namespace."""

    def __init__(
        self,
        *,
        ssh_transport: SshTransport | None = None,
        runner=subprocess.run,
    ) -> None:
        self.ssh_transport = ssh_transport or SshTransport()
        self.runner = runner

    def transfer(
        self,
        *,
        target: TransportTarget,
        request: ArtifactTransferRequest,
        timeout_seconds: int,
    ) -> ArtifactTransferResult:
        if target.transport != "ssh":
            raise ArtifactTransferError(
                "Artifact transfer requires SSH transport"
            )

        artifact_id = str(request.artifact_id or "").strip()
        if not _ARTIFACT_ID_RE.fullmatch(artifact_id):
            raise ArtifactTransferError("Invalid artifact id")

        source = Path(request.source)

        if not source.is_file():
            raise ArtifactTransferError(
                "Artifact source must be a regular file"
            )

        expected = str(request.expected_sha256 or "").strip().lower()

        if not _SHA256_RE.fullmatch(expected):
            raise ArtifactTransferError(
                "Invalid expected artifact SHA-256"
            )

        local_sha = file_sha256(source)

        if local_sha != expected:
            raise ArtifactTransferError(
                "Local artifact does not match reviewed SHA-256"
            )

        if not target.host or not target.username:
            raise ArtifactTransferError(
                "SSH target requires host and username"
            )

        if not target.known_hosts_file:
            raise ArtifactTransferError(
                "SSH target requires dedicated known_hosts_file"
            )

        if not os.path.isfile(target.known_hosts_file):
            raise ArtifactTransferError(
                "SSH known_hosts_file does not exist"
            )

        if target.identity_file and not os.path.isfile(
            target.identity_file
        ):
            raise ArtifactTransferError(
                "SSH identity_file does not exist"
            )

        remote_path = (
            f"{REMOTE_STAGE_ROOT}/{artifact_id}"
        )

        prepare = self.ssh_transport.execute(
            target=target,
            argv=[
                "/usr/bin/mkdir",
                "-p",
                REMOTE_STAGE_ROOT,
            ],
            timeout_seconds=min(timeout_seconds, 30),
            secrets=(),
        )

        if not prepare.ok:
            raise ArtifactTransferError(
                "Unable to prepare remote artifact staging"
            )

        command = [
            "scp",
            "-P",
            str(target.port),
            "-o",
            "BatchMode=yes",
            "-o",
            "IdentitiesOnly=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            "-o",
            f"UserKnownHostsFile={target.known_hosts_file}",
            "-o",
            "GlobalKnownHostsFile=/dev/null",
            "-o",
            "PasswordAuthentication=no",
            "-o",
            "KbdInteractiveAuthentication=no",
            "-o",
            "LogLevel=ERROR",
            "-o",
            f"ConnectTimeout={min(timeout_seconds, 15)}",
        ]

        if target.identity_file:
            command.extend([
                "-i",
                target.identity_file,
            ])

        command.extend([
            str(source),
            (
                f"{target.username}@{target.host}:"
                f"{remote_path}"
            ),
        ])

        started = time.perf_counter()

        try:
            completed = self.runner(
                command,
                capture_output=True,
                text=True,
                shell=False,
                timeout=timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise ArtifactTransferError(
                "Artifact transfer timed out"
            ) from exc

        duration_ms = round(
            (time.perf_counter() - started) * 1000
        )

        if completed.returncode != 0:
            raise ArtifactTransferError(
                "Artifact transfer failed"
            )

        verification = self.ssh_transport.execute(
            target=target,
            argv=[
                "/usr/bin/sha256sum",
                "--",
                remote_path,
            ],
            timeout_seconds=min(timeout_seconds, 30),
            secrets=(),
        )

        if not verification.ok:
            raise ArtifactTransferError(
                "Transferred artifact verification failed"
            )

        remote_sha = (
            verification.stdout
            .strip()
            .split(maxsplit=1)[0]
            .lower()
        )

        if remote_sha != expected:
            raise ArtifactTransferError(
                "Transferred artifact SHA-256 mismatch"
            )

        return ArtifactTransferResult(
            artifact_id=artifact_id,
            remote_path=remote_path,
            sha256=remote_sha,
            duration_ms=duration_ms,
            host_key_verified=verification.host_key_verified,
        )
