from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from backend.executors.blockchain_deployment_executor import (
    DeploymentRequest,
    DeploymentStepOutput,
)
from backend.services.blockchain_bootstrap_invocation_service import (
    BootstrapInvocationContext,
)
from backend.services.blockchain_deployment_release_service import (
    DeploymentReleaseContext,
)
from backend.transports.models import (
    TransportTarget,
)
from backend.transports.runtime_verification import (
    RuntimeVerificationRequest,
    RuntimeVerificationResult,
    SshRuntimeVerificationTransport,
)


@dataclass(frozen=True, slots=True)
class RuntimeVerificationContext:
    runtime_version: str
    source_revision: str
    payload_manifest_sha256: str


class BlockchainRuntimeVerificationService:
    def __init__(
        self,
        *,
        target: TransportTarget,
        transport: SshRuntimeVerificationTransport,
        timeout_seconds: int = 30,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError(
                "Runtime verification timeout must be positive"
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
                "Runtime verification target does not match deployment target"
            )

        if self._target.transport != "ssh":
            raise ValueError(
                "Runtime verification target must use SSH"
            )

        release = self._private_context(
            private,
            "resolve-release",
            DeploymentReleaseContext,
        )

        bootstrap = self._private_context(
            private,
            "invoke-bootstrap",
            BootstrapInvocationContext,
        )

        if bootstrap.runtime_version != release.runtime_version:
            raise ValueError(
                "Bootstrap runtime version does not match reviewed release"
            )

        if bootstrap.source_revision != release.source_revision:
            raise ValueError(
                "Bootstrap source revision does not match reviewed release"
            )

        if (
            bootstrap.payload_manifest_sha256
            != release.payload_manifest_sha256
        ):
            raise ValueError(
                "Bootstrap payload manifest does not match reviewed release"
            )

        typed_request = RuntimeVerificationRequest(
            runtime_version=release.runtime_version,
            source_revision=release.source_revision,
            payload_manifest_sha256=(
                release.payload_manifest_sha256
            ),
        )

        result = self._transport.verify(
            target=self._target,
            request=typed_request,
            timeout_seconds=self._timeout_seconds,
        )

        if not isinstance(
            result,
            RuntimeVerificationResult,
        ):
            raise ValueError(
                "Runtime verification transport returned invalid result"
            )

        if result.runtime_version != release.runtime_version:
            raise ValueError(
                "Verified runtime version does not match reviewed release"
            )

        if result.source_revision != release.source_revision:
            raise ValueError(
                "Verified source revision does not match reviewed release"
            )

        if (
            result.payload_manifest_sha256
            != release.payload_manifest_sha256
        ):
            raise ValueError(
                "Verified payload manifest does not match reviewed release"
            )

        if not result.executable_present:
            raise ValueError(
                "Verified runtime installer executable is unavailable"
            )

        if not result.host_key_verified:
            raise ValueError(
                "Runtime verification did not verify host key"
            )

        context = RuntimeVerificationContext(
            runtime_version=result.runtime_version,
            source_revision=result.source_revision,
            payload_manifest_sha256=(
                result.payload_manifest_sha256
            ),
        )

        evidence = {
            "runtimeVersion": result.runtime_version,
            "sourceRevision": result.source_revision,
            "payloadManifestSha256": (
                result.payload_manifest_sha256
            ),
            "executablePresent": result.executable_present,
            "durationMs": result.duration_ms,
            "hostKeyVerified": result.host_key_verified,
        }

        return DeploymentStepOutput(
            evidence=evidence,
            private=context,
        )
