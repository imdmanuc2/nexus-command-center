from __future__ import annotations

from dataclasses import dataclass
import json
import re
import time

from backend.services.blockchain_target_platform import (
    TargetPlatformProfile,
    UMBREL_TARGET_PROFILE,
)
from backend.transports.models import TransportTarget
from backend.transports.ssh_transport import SshTransport


_PROVIDER_ID_RE = re.compile(
    r"^[a-z0-9][a-z0-9-]{0,63}$"
)

INSTALLATION_CONTRACT = (
    "seymour.blockchain-installation"
)
INSTALLATION_CONTRACT_VERSION = 1


class InstallationVerificationError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class InstallationVerificationRequest:
    provider_id: str


@dataclass(frozen=True, slots=True)
class InstallationVerificationResult:
    contract: str
    contract_version: int
    operation_id: str
    provider_id: str
    storage_target_id: str
    status: str
    verified: bool
    state_verified: bool
    runtime_data_mount_matches: bool
    runtime_blocks_mount_matches: bool
    binding_mode: str
    recorded_at: str
    duration_ms: int
    host_key_verified: bool


class SshInstallationVerificationTransport:
    def __init__(
        self,
        *,
        profile: TargetPlatformProfile = UMBREL_TARGET_PROFILE,
        transport: SshTransport | None = None,
    ) -> None:
        self._profile = profile
        self._transport = transport or SshTransport()

    @staticmethod
    def _provider_id(value: str) -> str:
        normalized = str(value or "").strip()

        if not _PROVIDER_ID_RE.fullmatch(
            normalized
        ):
            raise ValueError(
                "provider_id is invalid"
            )

        return normalized

    @staticmethod
    def _required(
        payload: dict,
        name: str,
    ) -> str:
        value = str(
            payload.get(name) or ""
        ).strip()

        if not value:
            raise InstallationVerificationError(
                f"Installation evidence {name} is missing"
            )

        return value

    def verify(
        self,
        *,
        target: TransportTarget,
        request: InstallationVerificationRequest,
        timeout_seconds: int = 30,
    ) -> InstallationVerificationResult:
        if target.transport != "ssh":
            raise InstallationVerificationError(
                "Installation verification requires SSH"
            )

        if timeout_seconds <= 0:
            raise ValueError(
                "Installation verification timeout must be positive"
            )

        if self._profile.platform_id != "umbrel":
            raise InstallationVerificationError(
                "Unsupported target platform profile"
            )

        provider_id = self._provider_id(
            request.provider_id
        )

        executable = (
            self._profile.runtime_root.rstrip("/")
            + "/scripts/"
            + "seymour-blockchain-install-evidence"
        )

        started = time.monotonic()

        result = self._transport.execute(
            target=target,
            argv=[
                executable,
                "--provider-id",
                provider_id,
            ],
            timeout_seconds=timeout_seconds,
        )

        if not result.host_key_verified:
            raise InstallationVerificationError(
                "Installation verification host key was not verified"
            )

        if result.timed_out:
            raise InstallationVerificationError(
                "Installation verification timed out"
            )

        if result.exit_code != 0:
            raise InstallationVerificationError(
                "Provider installation evidence query failed"
            )

        try:
            payload = json.loads(
                result.stdout.strip()
            )
        except Exception as exc:
            raise InstallationVerificationError(
                "Installation evidence is invalid JSON"
            ) from exc

        if not isinstance(payload, dict):
            raise InstallationVerificationError(
                "Installation evidence is invalid"
            )

        if (
            payload.get("contract")
            != INSTALLATION_CONTRACT
        ):
            raise InstallationVerificationError(
                "Installation evidence contract mismatch"
            )

        if (
            payload.get("version")
            != INSTALLATION_CONTRACT_VERSION
        ):
            raise InstallationVerificationError(
                "Installation evidence contract version mismatch"
            )

        if payload.get("operation") != "install":
            raise InstallationVerificationError(
                "Installation evidence operation mismatch"
            )

        if payload.get("status") != "installed":
            raise InstallationVerificationError(
                "Installation evidence status is not installed"
            )

        operation_id = self._required(
            payload,
            "operationId",
        )

        evidence_provider_id = self._required(
            payload,
            "providerId",
        )

        storage_target_id = self._required(
            payload,
            "storageTargetId",
        )

        if evidence_provider_id != provider_id:
            raise InstallationVerificationError(
                "Installation evidence provider mismatch"
            )

        assertions = (
            ("verified", "verified"),
            (
                "stateVerified",
                "state verification",
            ),
            (
                "runtimeDataMountMatches",
                "runtime data mount verification",
            ),
            (
                "runtimeBlocksMountMatches",
                "runtime blocks mount verification",
            ),
        )

        for field, description in assertions:
            if payload.get(field) is not True:
                raise InstallationVerificationError(
                    "Installation evidence "
                    + description
                    + " failed"
                )

        binding_mode = self._required(
            payload,
            "bindingMode",
        )

        recorded_at = self._required(
            payload,
            "recordedAt",
        )

        duration_ms = max(
            0,
            int(
                (time.monotonic() - started)
                * 1000
            ),
        )

        return InstallationVerificationResult(
            contract=INSTALLATION_CONTRACT,
            contract_version=(
                INSTALLATION_CONTRACT_VERSION
            ),
            operation_id=operation_id,
            provider_id=evidence_provider_id,
            storage_target_id=storage_target_id,
            status="installed",
            verified=True,
            state_verified=True,
            runtime_data_mount_matches=True,
            runtime_blocks_mount_matches=True,
            binding_mode=binding_mode,
            recorded_at=recorded_at,
            duration_ms=duration_ms,
            host_key_verified=True,
        )
