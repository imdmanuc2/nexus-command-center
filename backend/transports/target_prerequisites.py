from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any

from backend.services.blockchain_target_platform import (
    TargetPlatformProfile,
)
from backend.transports.models import (
    TransportTarget,
)
from backend.transports.ssh_transport import SshTransport


class TargetPrerequisiteError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class TargetPrerequisiteResult:
    platform_id: str
    python_version: str
    tar_version: str
    checks: tuple[str, ...]
    duration_ms: int
    host_key_verified: bool


PYTHON_FEATURE_PROBE = (
    "import inspect,tarfile;"
    "p=inspect.signature("
    "tarfile.TarFile.extractall"
    ").parameters;"
    "print("
    "'filter=' + str('filter' in p) + "
    "';data=' + str(hasattr(tarfile,'data_filter'))"
    ")"
)


class SshTargetPrerequisiteTransport:
    def __init__(
        self,
        transport: SshTransport | None = None,
    ) -> None:
        self._transport = transport or SshTransport()

    @staticmethod
    def _run_checked(
        transport: Any,
        *,
        target: TransportTarget,
        argv: list[str],
        timeout_seconds: int,
        check_name: str,
    ):
        result = transport.execute(
            target=target,
            argv=argv,
            timeout_seconds=timeout_seconds,
        )

        if not result.host_key_verified:
            raise TargetPrerequisiteError(
                f"{check_name}: host key was not verified"
            )

        if result.timed_out:
            raise TargetPrerequisiteError(
                f"{check_name}: operation timed out"
            )

        if result.exit_code != 0:
            raise TargetPrerequisiteError(
                f"{check_name}: prerequisite check failed"
            )

        return result

    def verify(
        self,
        *,
        target: TransportTarget,
        profile: TargetPlatformProfile,
        timeout_seconds: int = 30,
    ) -> TargetPrerequisiteResult:
        if target.transport != "ssh":
            raise TargetPrerequisiteError(
                "Target prerequisite verification requires SSH"
            )

        if timeout_seconds <= 0:
            raise ValueError(
                "Target prerequisite timeout must be positive"
            )

        if profile.platform_id != "umbrel":
            raise TargetPrerequisiteError(
                "Unsupported target platform profile"
            )

        started = time.monotonic()

        checks: list[str] = []

        runtime_parent = (
            profile.runtime_root.rsplit("/", 1)[0]
        )
        staging_parent = (
            profile.staging_root.rsplit("/", 1)[0]
        )

        fixed_checks = (
            (
                "runtime-parent-exists",
                [
                    profile.test_path,
                    "-d",
                    runtime_parent,
                ],
            ),
            (
                "runtime-parent-writable",
                [
                    profile.test_path,
                    "-w",
                    runtime_parent,
                ],
            ),
            (
                "staging-parent-exists",
                [
                    profile.test_path,
                    "-d",
                    staging_parent,
                ],
            ),
            (
                "staging-parent-writable",
                [
                    profile.test_path,
                    "-w",
                    staging_parent,
                ],
            ),
            (
                "python3-executable",
                [
                    profile.test_path,
                    "-x",
                    profile.python3_path,
                ],
            ),
            (
                "tar-executable",
                [
                    profile.test_path,
                    "-x",
                    profile.tar_path,
                ],
            ),
            (
                "sha256sum-executable",
                [
                    profile.test_path,
                    "-x",
                    profile.sha256sum_path,
                ],
            ),
            (
                "rm-executable",
                [
                    profile.test_path,
                    "-x",
                    profile.rm_path,
                ],
            ),
        )

        for check_name, argv in fixed_checks:
            self._run_checked(
                self._transport,
                target=target,
                argv=argv,
                timeout_seconds=timeout_seconds,
                check_name=check_name,
            )
            checks.append(check_name)

        python_version_result = self._run_checked(
            self._transport,
            target=target,
            argv=[
                profile.python3_path,
                "--version",
            ],
            timeout_seconds=timeout_seconds,
            check_name="python-version",
        )
        checks.append("python-version")

        python_version = (
            python_version_result.stdout.strip()
            or python_version_result.stderr.strip()
        )

        if not python_version.startswith("Python "):
            raise TargetPrerequisiteError(
                "python-version: invalid Python version response"
            )

        feature_result = self._run_checked(
            self._transport,
            target=target,
            argv=[
                profile.python3_path,
                "-c",
                PYTHON_FEATURE_PROBE,
            ],
            timeout_seconds=timeout_seconds,
            check_name="python-tar-filter",
        )
        checks.append("python-tar-filter")

        feature_output = (
            feature_result.stdout.strip()
        )

        if feature_output != "filter=True;data=True":
            raise TargetPrerequisiteError(
                "python-tar-filter: required tar extraction "
                "filter support is unavailable"
            )

        tar_version_result = self._run_checked(
            self._transport,
            target=target,
            argv=[
                profile.tar_path,
                "--version",
            ],
            timeout_seconds=timeout_seconds,
            check_name="tar-version",
        )
        checks.append("tar-version")

        tar_lines = [
            line.strip()
            for line in tar_version_result.stdout.splitlines()
            if line.strip()
        ]

        if not tar_lines:
            raise TargetPrerequisiteError(
                "tar-version: invalid tar version response"
            )

        duration_ms = max(
            0,
            int(
                (time.monotonic() - started)
                * 1000
            ),
        )

        return TargetPrerequisiteResult(
            platform_id=profile.platform_id,
            python_version=python_version,
            tar_version=tar_lines[0],
            checks=tuple(checks),
            duration_ms=duration_ms,
            host_key_verified=True,
        )
