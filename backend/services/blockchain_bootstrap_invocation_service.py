from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from backend.executors.blockchain_deployment_executor import (
    DeploymentRequest,
    DeploymentStepOutput,
)
from backend.services.blockchain_bootstrap_transfer_service import (
    BootstrapTransferContext,
)
from backend.services.blockchain_deployment_release_service import (
    DeploymentReleaseContext,
)
from backend.services.blockchain_runtime_transfer_service import (
    RuntimeTransferContext,
)
from backend.transports.bootstrap_invocation import (
    BootstrapInvocationRequest,
    BootstrapInvocationResult,
    SshBootstrapInvocationTransport,
)
from backend.transports.models import TransportTarget


@dataclass(frozen=True, slots=True)
class BootstrapInvocationContext:
    runtime_version: str
    source_revision: str
    runtime_sha256: str
    payload_manifest_sha256: str


class BlockchainBootstrapInvocationService:
    def __init__(
        self,
        *,
        target: TransportTarget,
        transport: SshBootstrapInvocationTransport | None = None,
        timeout_seconds: int = 900,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError(
                "bootstrap invocation timeout must be positive"
            )

        self._target = target
        self._transport = (
            transport
            or SshBootstrapInvocationTransport()
        )
        self._timeout_seconds = timeout_seconds

    @staticmethod
    def _private(
        private_context: Mapping[str, Any],
        step_id: str,
        expected_type: type,
    ) -> Any:
        value = private_context.get(step_id)

        if not isinstance(value, expected_type):
            raise ValueError(
                f"Missing or invalid private {step_id} context"
            )

        return value

    def invoke(
        self,
        request: DeploymentRequest,
        evidence_context: dict[str, Any],
        private_context: Mapping[str, Any],
    ) -> DeploymentStepOutput:
        del evidence_context

        if self._target.asset_id != request.target_asset_id:
            raise ValueError(
                "Bootstrap invocation target asset mismatch"
            )

        if self._target.transport != "ssh":
            raise ValueError(
                "Bootstrap invocation requires SSH target"
            )

        release = self._private(
            private_context,
            "resolve-release",
            DeploymentReleaseContext,
        )

        bootstrap = self._private(
            private_context,
            "transfer-bootstrap",
            BootstrapTransferContext,
        )

        runtime = self._private(
            private_context,
            "transfer-runtime",
            RuntimeTransferContext,
        )

        if (
            bootstrap.artifact_id
            != release.bootstrap_artifact_id
        ):
            raise ValueError(
                "Bootstrap transfer identity does not match release"
            )

        if bootstrap.sha256 != release.bootstrap_sha256:
            raise ValueError(
                "Bootstrap transfer SHA does not match release"
            )

        if runtime.artifact_id != release.runtime_artifact_id:
            raise ValueError(
                "Runtime transfer identity does not match release"
            )

        if runtime.sha256 != release.runtime_sha256:
            raise ValueError(
                "Runtime transfer SHA does not match release"
            )

        result = self._transport.invoke(
            target=self._target,
            request=BootstrapInvocationRequest(
                bootstrap_artifact_id=(
                    release.bootstrap_artifact_id
                ),
                bootstrap_sha256=(
                    release.bootstrap_sha256
                ),
                runtime_artifact_id=(
                    release.runtime_artifact_id
                ),
                runtime_sha256=release.runtime_sha256,
                payload_manifest_sha256=(
                    release.payload_manifest_sha256
                ),
                runtime_version=release.runtime_version,
                source_revision=release.source_revision,
            ),
            timeout_seconds=self._timeout_seconds,
        )

        if not isinstance(
            result,
            BootstrapInvocationResult,
        ):
            raise ValueError(
                "Bootstrap invocation returned invalid result"
            )

        if result.bootstrap_sha256 != release.bootstrap_sha256:
            raise ValueError(
                "Bootstrap invocation SHA evidence mismatch"
            )

        if result.runtime_sha256 != release.runtime_sha256:
            raise ValueError(
                "Runtime invocation SHA evidence mismatch"
            )

        if (
            result.payload_manifest_sha256
            != release.payload_manifest_sha256
        ):
            raise ValueError(
                "Payload manifest invocation evidence mismatch"
            )

        if result.runtime_version != release.runtime_version:
            raise ValueError(
                "Runtime version invocation evidence mismatch"
            )

        if result.source_revision != release.source_revision:
            raise ValueError(
                "Source revision invocation evidence mismatch"
            )

        if result.exit_code != 0:
            raise ValueError(
                "Bootstrap invocation did not exit successfully"
            )

        if not result.host_key_verified:
            raise ValueError(
                "Bootstrap invocation host key was not verified"
            )

        private = BootstrapInvocationContext(
            runtime_version=result.runtime_version,
            source_revision=result.source_revision,
            runtime_sha256=result.runtime_sha256,
            payload_manifest_sha256=(
                result.payload_manifest_sha256
            ),
        )

        return DeploymentStepOutput(
            evidence={
                "runtimeVersion": result.runtime_version,
                "sourceRevision": result.source_revision,
                "runtimeSha256": result.runtime_sha256,
                "payloadManifestSha256": (
                    result.payload_manifest_sha256
                ),
                "durationMs": result.duration_ms,
                "exitCode": result.exit_code,
                "hostKeyVerified": (
                    result.host_key_verified
                ),
            },
            private=private,
        )
