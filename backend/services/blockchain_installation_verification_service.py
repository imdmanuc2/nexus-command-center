from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from backend.executors.blockchain_deployment_executor import (
    DeploymentRequest,
    DeploymentStepOutput,
)
from backend.services.blockchain_installer_invocation_service import (
    BlockchainInstallerInvocationContext,
)
from backend.transports.installation_verification import (
    INSTALLATION_CONTRACT,
    INSTALLATION_CONTRACT_VERSION,
    InstallationVerificationRequest,
    InstallationVerificationResult,
    SshInstallationVerificationTransport,
)
from backend.transports.models import TransportTarget


@dataclass(frozen=True, slots=True)
class InstallationVerificationContext:
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


class BlockchainInstallationVerificationService:
    def __init__(
        self,
        *,
        target: TransportTarget,
        transport: SshInstallationVerificationTransport,
        timeout_seconds: int = 30,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError(
                "Installation verification timeout must be positive"
            )

        self._target = target
        self._transport = transport
        self._timeout_seconds = timeout_seconds

    @staticmethod
    def _private_context(
        private: Mapping[str, object],
        step_id: str,
        expected_type: type,
    ):
        value = private.get(step_id)

        if not isinstance(value, expected_type):
            raise ValueError(
                f"Missing or invalid private context: {step_id}"
            )

        return value

    def execute(
        self,
        *,
        request: DeploymentRequest,
        private: Mapping[str, object],
    ) -> DeploymentStepOutput:
        if self._target.asset_id != request.target_asset_id:
            raise ValueError(
                "Installation verification target does not match deployment target"
            )

        if self._target.transport != "ssh":
            raise ValueError(
                "Installation verification target must use SSH"
            )

        installer = self._private_context(
            private,
            "invoke-installer",
            BlockchainInstallerInvocationContext,
        )

        if installer.provider_id != request.provider_id:
            raise ValueError(
                "Installer provider does not match deployment request"
            )

        if (
            installer.storage_target_id
            != request.storage_target_id
        ):
            raise ValueError(
                "Installer storage target does not match deployment request"
            )

        if not installer.operation_id:
            raise ValueError(
                "Installer operation ID is missing"
            )

        if installer.success is not True:
            raise ValueError(
                "Installer private state does not indicate success"
            )

        typed_request = InstallationVerificationRequest(
            provider_id=request.provider_id,
        )

        result = self._transport.verify(
            target=self._target,
            request=typed_request,
            timeout_seconds=self._timeout_seconds,
        )

        if not isinstance(
            result,
            InstallationVerificationResult,
        ):
            raise ValueError(
                "Installation verification transport returned invalid result"
            )

        if result.contract != INSTALLATION_CONTRACT:
            raise ValueError(
                "Verified installation contract mismatch"
            )

        if (
            result.contract_version
            != INSTALLATION_CONTRACT_VERSION
        ):
            raise ValueError(
                "Verified installation contract version mismatch"
            )

        if result.operation_id != installer.operation_id:
            raise ValueError(
                "Verified installation operation ID does not match installer invocation"
            )

        if result.provider_id != request.provider_id:
            raise ValueError(
                "Verified installation provider does not match deployment request"
            )

        if (
            result.storage_target_id
            != request.storage_target_id
        ):
            raise ValueError(
                "Verified installation storage target does not match deployment request"
            )

        if result.status != "installed":
            raise ValueError(
                "Verified installation status is not installed"
            )

        if result.verified is not True:
            raise ValueError(
                "Verified installation is not verified"
            )

        if result.state_verified is not True:
            raise ValueError(
                "Verified installation state is not verified"
            )

        if (
            result.runtime_data_mount_matches
            is not True
        ):
            raise ValueError(
                "Verified installation data mount does not match"
            )

        if (
            result.runtime_blocks_mount_matches
            is not True
        ):
            raise ValueError(
                "Verified installation blocks mount does not match"
            )

        if not result.binding_mode:
            raise ValueError(
                "Verified installation binding mode is missing"
            )

        if not result.recorded_at:
            raise ValueError(
                "Verified installation timestamp is missing"
            )

        if not result.host_key_verified:
            raise ValueError(
                "Installation verification did not verify host key"
            )

        context = InstallationVerificationContext(
            contract=result.contract,
            contract_version=result.contract_version,
            operation_id=result.operation_id,
            provider_id=result.provider_id,
            storage_target_id=(
                result.storage_target_id
            ),
            status=result.status,
            verified=result.verified,
            state_verified=result.state_verified,
            runtime_data_mount_matches=(
                result.runtime_data_mount_matches
            ),
            runtime_blocks_mount_matches=(
                result.runtime_blocks_mount_matches
            ),
            binding_mode=result.binding_mode,
            recorded_at=result.recorded_at,
        )

        evidence = {
            "contract": result.contract,
            "contractVersion": result.contract_version,
            "operationId": result.operation_id,
            "providerId": result.provider_id,
            "storageTargetId": (
                result.storage_target_id
            ),
            "status": result.status,
            "verified": result.verified,
            "stateVerified": (
                result.state_verified
            ),
            "runtimeDataMountMatches": (
                result.runtime_data_mount_matches
            ),
            "runtimeBlocksMountMatches": (
                result.runtime_blocks_mount_matches
            ),
            "bindingMode": result.binding_mode,
            "recordedAt": result.recorded_at,
            "durationMs": result.duration_ms,
            "hostKeyVerified": (
                result.host_key_verified
            ),
        }

        return DeploymentStepOutput(
            evidence=evidence,
            private=context,
        )
