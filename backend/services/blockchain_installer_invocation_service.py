from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from backend.executors.blockchain_deployment_executor import (
    DeploymentRequest,
    DeploymentStepOutput,
)
from backend.services.blockchain_runtime_verification_service import (
    RuntimeVerificationContext,
)
from backend.transports.blockchain_installer_invocation import (
    BlockchainInstallerInvocationRequest,
    BlockchainInstallerInvocationResult,
    SshBlockchainInstallerInvocationTransport,
)
from backend.transports.models import TransportTarget


@dataclass(frozen=True, slots=True)
class BlockchainInstallerInvocationContext:
    provider_id: str
    storage_target_id: str
    operation_id: str
    success: bool


class BlockchainInstallerInvocationService:
    def __init__(
        self,
        *,
        target: TransportTarget,
        transport: SshBlockchainInstallerInvocationTransport,
        timeout_seconds: int = 900,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError(
                "Blockchain installer timeout must be positive"
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
                "Installer invocation target does not match deployment target"
            )

        if self._target.transport != "ssh":
            raise ValueError(
                "Installer invocation target must use SSH"
            )

        runtime = self._private_context(
            private,
            "verify-runtime",
            RuntimeVerificationContext,
        )

        if not runtime.runtime_version:
            raise ValueError(
                "Verified runtime version is missing"
            )

        if not runtime.source_revision:
            raise ValueError(
                "Verified runtime source revision is missing"
            )

        if not runtime.payload_manifest_sha256:
            raise ValueError(
                "Verified runtime payload manifest is missing"
            )

        typed_request = BlockchainInstallerInvocationRequest(
            provider_id=request.provider_id,
            storage_target_id=request.storage_target_id,
        )

        result = self._transport.invoke(
            target=self._target,
            request=typed_request,
            timeout_seconds=self._timeout_seconds,
        )

        if not isinstance(
            result,
            BlockchainInstallerInvocationResult,
        ):
            raise ValueError(
                "Installer invocation transport returned invalid result"
            )

        if result.provider_id != request.provider_id:
            raise ValueError(
                "Installer result provider does not match deployment request"
            )

        if result.storage_target_id != request.storage_target_id:
            raise ValueError(
                "Installer result storage target does not match deployment request"
            )

        if result.success is not True:
            raise ValueError(
                "Installer invocation did not report success"
            )

        if result.exit_code != 0:
            raise ValueError(
                "Installer invocation returned nonzero exit code"
            )

        if not result.host_key_verified:
            raise ValueError(
                "Installer invocation did not verify host key"
            )

        operation_id = str(
            result.result.get("operationId")
            or ""
        ).strip()

        if not operation_id:
            raise ValueError(
                "Installer invocation result is missing operationId"
            )

        context = BlockchainInstallerInvocationContext(
            provider_id=result.provider_id,
            storage_target_id=result.storage_target_id,
            operation_id=operation_id,
            success=True,
        )

        evidence = {
            "providerId": result.provider_id,
            "storageTargetId": result.storage_target_id,
            "success": True,
            "durationMs": result.duration_ms,
            "exitCode": result.exit_code,
            "hostKeyVerified": result.host_key_verified,
        }

        return DeploymentStepOutput(
            evidence=evidence,
            private=context,
        )
