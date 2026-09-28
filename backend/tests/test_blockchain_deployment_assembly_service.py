from __future__ import annotations

from backend.services.blockchain_deployment_storage_service import DeploymentStorageContext

import json
import unittest

from backend.executors.blockchain_deployment_executor import (
    BlockchainDeploymentExecutor,
    DeploymentRequest,
)
from backend.services.blockchain_deployment_assembly_service import (
    BlockchainDeploymentAssemblyError,
    BlockchainDeploymentAssemblyService,
)
from backend.services.blockchain_deployment_preflight_service import (
    BlockchainDeploymentPreflightContext,
    BlockchainDeploymentPreflightResult,
)
from backend.services.blockchain_target_platform import (
    TargetPlatformProfile,
    UMBREL_TARGET_PROFILE,
)
from backend.transports.artifact_transfer import (
    ArtifactTransferResult,
)
from backend.transports.blockchain_installer_invocation import (
    BlockchainInstallerInvocationResult,
)
from backend.transports.bootstrap_invocation import (
    BootstrapInvocationResult,
)
from backend.transports.installation_verification import (
    INSTALLATION_CONTRACT,
    INSTALLATION_CONTRACT_VERSION,
    InstallationVerificationResult,
)
from backend.transports.models import (
    TransportTarget,
)
from backend.transports.runtime_verification import (
    RuntimeVerificationResult,
)
from backend.transports.target_prerequisites import (
    TargetPrerequisiteResult,
)


class FakeArtifactTransport:
    def __init__(self):
        self.calls = []

    def transfer(
        self,
        *,
        target,
        request,
        timeout_seconds,
    ):
        self.calls.append({
            "target": target,
            "request": request,
            "timeout": timeout_seconds,
        })

        return ArtifactTransferResult(
            artifact_id=request.artifact_id,
            remote_path=(
                "/home/umbrel/.seymour-artifacts/"
                + request.artifact_id
            ),
            sha256=request.expected_sha256,
            duration_ms=3,
            host_key_verified=True,
        )


class FakeBootstrapTransport:
    def __init__(self):
        self.calls = []

    def invoke(
        self,
        *,
        target,
        request,
        timeout_seconds,
    ):
        self.calls.append({
            "target": target,
            "request": request,
            "timeout": timeout_seconds,
        })

        return BootstrapInvocationResult(
            bootstrap_sha256=(
                request.bootstrap_sha256
            ),
            runtime_sha256=(
                request.runtime_sha256
            ),
            payload_manifest_sha256=(
                request.payload_manifest_sha256
            ),
            runtime_version=(
                request.runtime_version
            ),
            source_revision=(
                request.source_revision
            ),
            duration_ms=4,
            exit_code=0,
            host_key_verified=True,
            result={
                "operationId": "op-offline-bootstrap",
                "operation": "install",
                "runtimeVersion": (
                    request.runtime_version
                ),
                "sourceRevision": (
                    request.source_revision
                ),
                "payloadManifestSha256": (
                    request.payload_manifest_sha256
                ),
                "status": "installed",
                "previousRuntimeAvailable": False,
            },
        )


class FakeRuntimeVerificationTransport:
    def __init__(self):
        self.calls = []

    def verify(
        self,
        *,
        target,
        request,
        timeout_seconds,
    ):
        self.calls.append({
            "target": target,
            "request": request,
            "timeout": timeout_seconds,
        })

        return RuntimeVerificationResult(
            runtime_version=(
                request.runtime_version
            ),
            source_revision=(
                request.source_revision
            ),
            payload_manifest_sha256=(
                request.payload_manifest_sha256
            ),
            executable_present=True,
            duration_ms=5,
            host_key_verified=True,
        )


class FakeInstallerTransport:
    def __init__(self):
        self.calls = []

    def invoke(
        self,
        *,
        target,
        request,
        timeout_seconds,
    ):
        self.calls.append({
            "target": target,
            "request": request,
            "timeout": timeout_seconds,
        })

        return BlockchainInstallerInvocationResult(
            provider_id=request.provider_id,
            storage_target_id=(
                request.storage_target_id
            ),
            success=True,
            duration_ms=6,
            exit_code=0,
            host_key_verified=True,
            result={
                "operationId": "op-offline-install",
                "status": "succeeded",
                "result": {},
                "verification": {
                    "verified": True,
                    "evidence": {},
                    "error": None,
                },
                "error": None,
            },
        )


class FakeInstallationVerificationTransport:
    def __init__(self):
        self.calls = []

    def verify(
        self,
        *,
        target,
        request,
        timeout_seconds,
    ):
        self.calls.append({
            "target": target,
            "request": request,
            "timeout": timeout_seconds,
        })

        return InstallationVerificationResult(
            contract=INSTALLATION_CONTRACT,
            contract_version=(
                INSTALLATION_CONTRACT_VERSION
            ),
            operation_id="op-offline-install",
            provider_id=request.provider_id,
            storage_target_id="storage-main",
            status="installed",
            verified=True,
            state_verified=True,
            runtime_data_mount_matches=True,
            runtime_blocks_mount_matches=True,
            binding_mode="single-path",
            recorded_at=(
                "2026-09-10T21:00:00+00:00"
            ),
            duration_ms=7,
            host_key_verified=True,
        )


def target():
    return TransportTarget(
        asset_id="asset-managed-1",
        transport="ssh",
        host="192.0.2.10",
        port=22,
        username="umbrel",
        identity_file="/private/identity",
        known_hosts_file="/private/known_hosts",
    )


def prerequisites(
    *,
    platform_id="umbrel",
    host_key_verified=True,
    checks=None,
):
    if checks is None:
        checks = (
            "runtime-parent-exists",
            "runtime-parent-writable",
            "staging-parent-exists",
            "staging-parent-writable",
            "python3-executable",
            "tar-executable",
            "sha256sum-executable",
            "rm-executable",
            "python-version",
            "python-tar-filter",
            "tar-version",
        )

    return TargetPrerequisiteResult(
        platform_id=platform_id,
        python_version="Python 3.11.9",
        tar_version="tar (GNU tar) 1.34",
        checks=checks,
        duration_ms=2,
        host_key_verified=host_key_verified,
    )


def preflight(
    *,
    resolved_target=None,
    profile=UMBREL_TARGET_PROFILE,
    prerequisite_result=None,
):
    resolved_target = (
        resolved_target
        if resolved_target is not None
        else target()
    )

    prerequisite_result = (
        prerequisite_result
        if prerequisite_result is not None
        else prerequisites()
    )

    return BlockchainDeploymentPreflightResult(
        context=BlockchainDeploymentPreflightContext(
            target=resolved_target,
            profile=profile,
            storage=DeploymentStorageContext(
                storage_asset_id="storage-main",
                storage_asset_type="storage",
                target_asset_id=(resolved_target).asset_id,
                storage_source="/dev/sda6",
                storage_filesystem="ext4",
                storage_mount_path="/private/not-public",
            ),
            prerequisites=prerequisite_result,
        ),
        evidence={
            "targetAssetId": (
                resolved_target.asset_id
            ),
            "transport": "ssh",
            "deploymentPlatformId": (
                profile.platform_id
            ),
            "prerequisites": {
                "checks": list(
                    prerequisite_result.checks
                ),
                "pythonVersion": (
                    prerequisite_result.python_version
                ),
                "tarVersion": (
                    prerequisite_result.tar_version
                ),
                "durationMs": (
                    prerequisite_result.duration_ms
                ),
                "hostKeyVerified": (
                    prerequisite_result.host_key_verified
                ),
            },
        },
    )


class BlockchainDeploymentAssemblyServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.request = DeploymentRequest(
            provider_id="bitcoin-mainnet",
            storage_target_id="storage-main",
            target_asset_id="asset-managed-1",
            correlation_id="corr-offline",
            approved_by="approval-offline",
        )

        self.artifacts = FakeArtifactTransport()
        self.bootstrap = FakeBootstrapTransport()
        self.runtime_verify = (
            FakeRuntimeVerificationTransport()
        )
        self.installer = FakeInstallerTransport()
        self.install_verify = (
            FakeInstallationVerificationTransport()
        )

        self.profile_factory_calls = []

        def runtime_factory(profile):
            self.profile_factory_calls.append(
                ("runtime", profile)
            )
            return self.runtime_verify

        def installer_factory(profile):
            self.profile_factory_calls.append(
                ("installer", profile)
            )
            return self.installer

        def installation_factory(profile):
            self.profile_factory_calls.append(
                ("installation", profile)
            )
            return self.install_verify

        self.assembler = (
            BlockchainDeploymentAssemblyService(
                artifact_transport_factory=(
                    lambda: self.artifacts
                ),
                bootstrap_transport_factory=(
                    lambda: self.bootstrap
                ),
                runtime_verification_transport_factory=(
                    runtime_factory
                ),
                installer_transport_factory=(
                    installer_factory
                ),
                installation_verification_transport_factory=(
                    installation_factory
                ),
            )
        )

    def test_full_seven_step_execution_with_fake_transports(self):
        executor = self.assembler.assemble(
            request=self.request,
            preflight=preflight(),
        )

        self.assertIsInstance(
            executor,
            BlockchainDeploymentExecutor,
        )

        result = executor.execute(
            self.request
        )

        self.assertTrue(
            result.ok,
            result.error,
        )

        self.assertEqual(
            result.status,
            "completed",
        )

        self.assertEqual(
            tuple(
                step.step_id
                for step in result.steps
            ),
            BlockchainDeploymentExecutor.STEP_IDS,
        )

        self.assertEqual(
            len(result.steps),
            7,
        )

        self.assertTrue(
            all(
                step.status == "completed"
                for step in result.steps
            )
        )

        self.assertEqual(
            len(self.artifacts.calls),
            2,
        )

        self.assertEqual(
            len(self.bootstrap.calls),
            1,
        )

        self.assertEqual(
            len(self.runtime_verify.calls),
            1,
        )

        self.assertEqual(
            len(self.installer.calls),
            1,
        )

        self.assertEqual(
            len(self.install_verify.calls),
            1,
        )

        final = result.steps[-1].evidence

        self.assertEqual(
            final["contract"],
            INSTALLATION_CONTRACT,
        )

        self.assertEqual(
            final["operationId"],
            "op-offline-install",
        )

        self.assertEqual(
            final["providerId"],
            "bitcoin-mainnet",
        )

        self.assertEqual(
            final["storageTargetId"],
            "storage-main",
        )

        self.assertTrue(
            final["verified"]
        )

    def test_reviewed_release_is_real_promoted_runtime(self):
        executor = self.assembler.assemble(
            request=self.request,
            preflight=preflight(),
        )

        result = executor.execute(
            self.request
        )

        release = result.steps[0].evidence

        self.assertEqual(
            release["runtimeVersion"],
            "1.0.0",
        )

        self.assertEqual(
            release["sourceRevision"],
            "850ceec68411aa219585e82f45f8a144609d70bc",
        )

        self.assertEqual(
            release["runtime"]["sha256"],
            "a7e54254d8b89dc70a9a84ce88750e0e18500e3b2ef36287c12c246b3c7ede26",
        )

        self.assertEqual(
            release["runtime"][
                "payloadManifestSha256"
            ],
            "3fa83dd180c1cc5271f07e2190ef28141c869dca477c0aa3017bb4b7362d1a13",
        )

    def test_profile_aware_transports_receive_exact_preflight_profile(self):
        self.assembler.assemble(
            request=self.request,
            preflight=preflight(),
        )

        self.assertEqual(
            self.profile_factory_calls,
            [
                (
                    "runtime",
                    UMBREL_TARGET_PROFILE,
                ),
                (
                    "installer",
                    UMBREL_TARGET_PROFILE,
                ),
                (
                    "installation",
                    UMBREL_TARGET_PROFILE,
                ),
            ],
        )

    def test_mutated_umbrel_profile_fails_closed(self):
        mutated = TargetPlatformProfile(
            platform_id="umbrel",
            staging_root="/tmp/forbidden-stage",
            runtime_root=(
                UMBREL_TARGET_PROFILE.runtime_root
            ),
            lifecycle_adapter_id="umbrel",
            test_path="/usr/bin/test",
            python3_path="/usr/bin/python3",
            tar_path="/usr/bin/tar",
            sha256sum_path="/usr/bin/sha256sum",
            rm_path="/usr/bin/rm",
        )

        with self.assertRaisesRegex(
            BlockchainDeploymentAssemblyError,
            "canonical Umbrel target profile",
        ):
            self.assembler.assemble(
                request=self.request,
                preflight=preflight(
                    profile=mutated,
                ),
            )

        self.assertEqual(
            self.artifacts.calls,
            [],
        )

    def test_target_identity_mismatch_fails_before_transport_construction(self):
        wrong = TransportTarget(
            asset_id="asset-other",
            transport="ssh",
            host="192.0.2.10",
            username="umbrel",
            known_hosts_file="/private/known_hosts",
        )

        with self.assertRaisesRegex(
            BlockchainDeploymentAssemblyError,
            "target does not match request",
        ):
            self.assembler.assemble(
                request=self.request,
                preflight=preflight(
                    resolved_target=wrong,
                ),
            )

        self.assertEqual(
            self.profile_factory_calls,
            [],
        )

    def test_unverified_preflight_host_key_fails_closed(self):
        with self.assertRaisesRegex(
            BlockchainDeploymentAssemblyError,
            "did not verify host key",
        ):
            self.assembler.assemble(
                request=self.request,
                preflight=preflight(
                    prerequisite_result=(
                        prerequisites(
                            host_key_verified=False
                        )
                    ),
                ),
            )

    def test_preflight_remains_outside_durable_steps(self):
        self.assertEqual(
            BlockchainDeploymentExecutor.STEP_IDS,
            (
                "resolve-release",
                "transfer-bootstrap",
                "transfer-runtime",
                "invoke-bootstrap",
                "verify-runtime",
                "invoke-installer",
                "verify-installation",
            ),
        )

        self.assertNotIn(
            "preflight",
            BlockchainDeploymentExecutor.STEP_IDS,
        )

    def test_result_evidence_does_not_expose_transport_secrets(self):
        executor = self.assembler.assemble(
            request=self.request,
            preflight=preflight(),
        )

        result = executor.execute(
            self.request
        )

        encoded = json.dumps(
            result.to_dict()
        )

        for forbidden in (
            "192.0.2.10",
            "/private/",
            "known_hosts",
            "identity_file",
            "/home/umbrel",
        ):
            self.assertNotIn(
                forbidden,
                encoded,
            )


if __name__ == "__main__":
    unittest.main()
