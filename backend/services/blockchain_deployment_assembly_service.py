from __future__ import annotations

from collections.abc import Callable

from backend.executors.blockchain_deployment_executor import (
    BlockchainDeploymentExecutor,
    DeploymentRequest,
)
from backend.services.blockchain_bootstrap_invocation_service import (
    BlockchainBootstrapInvocationService,
)
from backend.services.blockchain_bootstrap_transfer_service import (
    BlockchainBootstrapTransferService,
)
from backend.services.blockchain_deployment_preflight_service import (
    BlockchainDeploymentPreflightResult,
)
from backend.services.blockchain_deployment_release_service import (
    BlockchainDeploymentReleaseService,
)
from backend.services.blockchain_installation_verification_service import (
    BlockchainInstallationVerificationService,
)
from backend.services.blockchain_installer_invocation_service import (
    BlockchainInstallerInvocationService,
)
from backend.services.blockchain_runtime_transfer_service import (
    BlockchainRuntimeTransferService,
)
from backend.services.blockchain_runtime_verification_service import (
    BlockchainRuntimeVerificationService,
)
from backend.services.blockchain_target_platform import (
    UMBREL_TARGET_PROFILE,
)
from backend.transports.artifact_transfer import (
    SshArtifactTransport,
)
from backend.transports.blockchain_installer_invocation import (
    SshBlockchainInstallerInvocationTransport,
)
from backend.transports.bootstrap_invocation import (
    SshBootstrapInvocationTransport,
)
from backend.transports.installation_verification import (
    SshInstallationVerificationTransport,
)
from backend.transports.runtime_verification import (
    SshRuntimeVerificationTransport,
)


class BlockchainDeploymentAssemblyError(RuntimeError):
    pass


class BlockchainDeploymentAssemblyService:
    """
    Construct the reviewed seven-step deployment executor from a
    successful deployment preflight result.

    Preflight itself is intentionally not a durable deployment step.

    No target address, SSH identity, known-hosts path, or target
    filesystem path is accepted from public deployment parameters.
    Those values come only from the reviewed private preflight context.
    """

    def __init__(
        self,
        *,
        release_service: (
            BlockchainDeploymentReleaseService | None
        ) = None,
        artifact_transport_factory: Callable[
            [], object
        ] | None = None,
        bootstrap_transport_factory: Callable[
            [], object
        ] | None = None,
        runtime_verification_transport_factory: Callable[
            [object], object
        ] | None = None,
        installer_transport_factory: Callable[
            [object], object
        ] | None = None,
        installation_verification_transport_factory: Callable[
            [object], object
        ] | None = None,
    ) -> None:
        self._release_service = (
            release_service
            or BlockchainDeploymentReleaseService()
        )

        self._artifact_transport_factory = (
            artifact_transport_factory
            or (lambda: SshArtifactTransport())
        )

        self._bootstrap_transport_factory = (
            bootstrap_transport_factory
            or (
                lambda:
                SshBootstrapInvocationTransport()
            )
        )

        self._runtime_verification_transport_factory = (
            runtime_verification_transport_factory
            or (
                lambda profile:
                SshRuntimeVerificationTransport(
                    profile=profile
                )
            )
        )

        self._installer_transport_factory = (
            installer_transport_factory
            or (
                lambda profile:
                SshBlockchainInstallerInvocationTransport(
                    profile=profile
                )
            )
        )

        self._installation_verification_transport_factory = (
            installation_verification_transport_factory
            or (
                lambda profile:
                SshInstallationVerificationTransport(
                    profile=profile
                )
            )
        )

    @staticmethod
    def _validate_preflight(
        *,
        request: DeploymentRequest,
        preflight: BlockchainDeploymentPreflightResult,
    ) -> None:
        if not isinstance(
            preflight,
            BlockchainDeploymentPreflightResult,
        ):
            raise BlockchainDeploymentAssemblyError(
                "Deployment assembly requires successful preflight result"
            )

        context = preflight.context
        target = context.target
        profile = context.profile
        prerequisites = context.prerequisites

        if target.asset_id != request.target_asset_id:
            raise BlockchainDeploymentAssemblyError(
                "Deployment preflight target does not match request"
            )

        if target.transport != "ssh":
            raise BlockchainDeploymentAssemblyError(
                "Deployment assembly requires SSH target"
            )

        # Artifact transfer and bootstrap invocation currently own the
        # canonical Umbrel staging namespace internally. Therefore the
        # complete profile must be the reviewed canonical profile, not
        # merely another profile carrying platform_id='umbrel'.
        if profile != UMBREL_TARGET_PROFILE:
            raise BlockchainDeploymentAssemblyError(
                "Deployment assembly requires canonical Umbrel target profile"
            )

        if prerequisites.platform_id != profile.platform_id:
            raise BlockchainDeploymentAssemblyError(
                "Deployment prerequisite platform does not match target profile"
            )

        if prerequisites.host_key_verified is not True:
            raise BlockchainDeploymentAssemblyError(
                "Deployment prerequisites did not verify host key"
            )

        if not prerequisites.checks:
            raise BlockchainDeploymentAssemblyError(
                "Deployment prerequisite checks are missing"
            )

    def assemble(
        self,
        *,
        request: DeploymentRequest,
        preflight: BlockchainDeploymentPreflightResult,
        execution_control: Callable[
            [DeploymentRequest, str, int, int],
            None,
        ]
        | None = None,
    ) -> BlockchainDeploymentExecutor:
        self._validate_preflight(
            request=request,
            preflight=preflight,
        )

        target = preflight.context.target
        profile = preflight.context.profile

        artifact_transport = (
            self._artifact_transport_factory()
        )

        bootstrap_transport = (
            self._bootstrap_transport_factory()
        )

        runtime_verification_transport = (
            self._runtime_verification_transport_factory(
                profile
            )
        )

        installer_transport = (
            self._installer_transport_factory(
                profile
            )
        )

        installation_verification_transport = (
            self._installation_verification_transport_factory(
                profile
            )
        )

        bootstrap_transfer = (
            BlockchainBootstrapTransferService(
                target=target,
                transport=artifact_transport,
            )
        )

        runtime_transfer = (
            BlockchainRuntimeTransferService(
                target=target,
                transport=artifact_transport,
            )
        )

        bootstrap_invocation = (
            BlockchainBootstrapInvocationService(
                target=target,
                transport=bootstrap_transport,
            )
        )

        runtime_verification = (
            BlockchainRuntimeVerificationService(
                target=target,
                transport=(
                    runtime_verification_transport
                ),
            )
        )

        installer_invocation = (
            BlockchainInstallerInvocationService(
                target=target,
                transport=installer_transport,
            )
        )

        installation_verification = (
            BlockchainInstallationVerificationService(
                target=target,
                transport=(
                    installation_verification_transport
                ),
            )
        )

        def verify_runtime(
            deployment_request,
            evidence_context,
            private_context,
        ):
            del evidence_context

            return runtime_verification.execute(
                request=deployment_request,
                private=private_context,
            )

        def invoke_installer(
            deployment_request,
            evidence_context,
            private_context,
        ):
            del evidence_context

            return installer_invocation.execute(
                request=deployment_request,
                private=private_context,
            )

        def verify_installation(
            deployment_request,
            evidence_context,
            private_context,
        ):
            del evidence_context

            return installation_verification.execute(
                request=deployment_request,
                private=private_context,
            )

        return BlockchainDeploymentExecutor(
            resolve_release=(
                self._release_service.resolve_step
            ),
            transfer_bootstrap=(
                bootstrap_transfer.transfer
            ),
            transfer_runtime=(
                runtime_transfer.transfer
            ),
            invoke_bootstrap=(
                bootstrap_invocation.invoke
            ),
            verify_runtime=verify_runtime,
            invoke_installer=invoke_installer,
            verify_installation=verify_installation,
            execution_control=execution_control,
        )
