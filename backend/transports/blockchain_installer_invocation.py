from __future__ import annotations

from dataclasses import dataclass
import json
import re
import time
from typing import Any

from backend.services.blockchain_target_platform import (
    TargetPlatformProfile,
    UMBREL_TARGET_PROFILE,
)
from backend.transports.models import (
    TransportTarget,
)
from backend.transports.ssh_transport import (
    SshTransport,
)


_PROVIDER_ID_RE = re.compile(
    r"^[a-z0-9][a-z0-9-]{0,63}$"
)

_STORAGE_TARGET_ID_RE = re.compile(
    r"^[A-Za-z0-9_.:-]{1,128}$"
)


class BlockchainInstallerInvocationError(
    RuntimeError
):
    pass


@dataclass(frozen=True, slots=True)
class BlockchainInstallerInvocationRequest:
    provider_id: str
    storage_target_id: str


@dataclass(frozen=True, slots=True)
class BlockchainInstallerInvocationResult:
    provider_id: str
    storage_target_id: str
    success: bool
    duration_ms: int
    exit_code: int
    host_key_verified: bool
    result: dict[str, object]


class SshBlockchainInstallerInvocationTransport:
    def __init__(
        self,
        *,
        profile: TargetPlatformProfile = (
            UMBREL_TARGET_PROFILE
        ),
        transport: SshTransport | None = None,
    ) -> None:
        self._profile = profile
        self._transport = (
            transport or SshTransport()
        )

    @staticmethod
    def _validate_provider_id(
        value: str,
    ) -> str:
        normalized = str(value or "").strip()

        if not _PROVIDER_ID_RE.fullmatch(
            normalized
        ):
            raise ValueError(
                "Invalid provider_id"
            )

        return normalized

    @staticmethod
    def _validate_storage_target_id(
        value: str,
    ) -> str:
        normalized = str(value or "").strip()

        if not _STORAGE_TARGET_ID_RE.fullmatch(
            normalized
        ):
            raise ValueError(
                "Invalid storage_target_id"
            )

        return normalized

    def invoke(
        self,
        *,
        target: TransportTarget,
        request: (
            BlockchainInstallerInvocationRequest
        ),
        timeout_seconds: int = 900,
    ) -> BlockchainInstallerInvocationResult:
        if target.transport != "ssh":
            raise BlockchainInstallerInvocationError(
                "Blockchain installer invocation requires SSH"
            )

        if timeout_seconds <= 0:
            raise ValueError(
                "Blockchain installer timeout must be positive"
            )

        if self._profile.platform_id != "umbrel":
            raise BlockchainInstallerInvocationError(
                "Unsupported target platform profile"
            )

        provider_id = (
            self._validate_provider_id(
                request.provider_id
            )
        )

        storage_target_id = (
            self._validate_storage_target_id(
                request.storage_target_id
            )
        )

        executable = (
            self._profile.runtime_root
            + "/scripts/seymour-blockchain-install"
        )

        argv = [
            executable,
            "--execute",
            "--provider-id",
            provider_id,
            "--storage-target-id",
            storage_target_id,
        ]

        started = time.monotonic()

        result = self._transport.execute(
            target=target,
            argv=argv,
            timeout_seconds=timeout_seconds,
        )

        if not result.host_key_verified:
            raise BlockchainInstallerInvocationError(
                "Installer invocation host key was not verified"
            )

        if result.timed_out:
            raise BlockchainInstallerInvocationError(
                "Installer invocation timed out"
            )

        if result.exit_code != 0:
            raise BlockchainInstallerInvocationError(
                "Installer invocation failed"
            )

        try:
            payload = json.loads(
                result.stdout.strip()
            )
        except Exception as exc:
            raise BlockchainInstallerInvocationError(
                "Installer invocation returned invalid JSON"
            ) from exc

        if not isinstance(payload, dict):
            raise BlockchainInstallerInvocationError(
                "Installer invocation returned invalid result"
            )

        status = str(
            payload.get("status") or ""
        ).strip()

        if status != "succeeded":
            raise BlockchainInstallerInvocationError(
                "Installer did not report succeeded status"
            )

        operation_id = str(
            payload.get("operationId") or ""
        ).strip()

        if not operation_id:
            raise BlockchainInstallerInvocationError(
                "Installer result is missing operationId"
            )

        verification = payload.get(
            "verification"
        )

        if not isinstance(
            verification,
            dict,
        ):
            raise BlockchainInstallerInvocationError(
                "Installer result is missing verification"
            )

        if (
            verification.get("verified")
            is not True
        ):
            raise BlockchainInstallerInvocationError(
                "Installer verification did not succeed"
            )

        duration_ms = max(
            0,
            int(
                (
                    time.monotonic()
                    - started
                )
                * 1000
            ),
        )

        return BlockchainInstallerInvocationResult(
            provider_id=provider_id,
            storage_target_id=storage_target_id,
            success=True,
            duration_ms=duration_ms,
            exit_code=result.exit_code,
            host_key_verified=True,
            result=payload,
        )
