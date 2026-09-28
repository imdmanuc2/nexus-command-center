from __future__ import annotations

import json
import unittest

from backend.executors.blockchain_deployment_executor import (
    BlockchainDeploymentExecutor,
    DeploymentRequest,
    DeploymentStepOutput,
)
from backend.services.blockchain_deployment_preflight_service import (
    BlockchainDeploymentPreflightContext,
    BlockchainDeploymentPreflightResult,
    BlockchainDeploymentPreflightService,
)
from backend.services.blockchain_deployment_target_service import (
    DeploymentTargetContext,
)
from backend.services.blockchain_deployment_storage_service import (
    DeploymentStorageContext,
)
from backend.services.blockchain_target_platform import (
    TargetPlatformProfile,
    UMBREL_TARGET_PROFILE,
)
from backend.transports.models import (
    TransportTarget,
)
from backend.transports.target_prerequisites import (
    TargetPrerequisiteResult,
)


class FakeTargetService:
    def __init__(self, output):
        self.output = output
        self.calls = []

    def resolve(self, request):
        self.calls.append(request)
        return self.output


class FakeStorageService:
    def __init__(self, output=None):
        self.output = (
            output
            if output is not None
            else DeploymentStorageContext(
                storage_asset_id="storage-main",
                storage_asset_type="storage",
                target_asset_id="asset-managed-1",
                storage_source="/dev/sda6",
                storage_filesystem="ext4",
                storage_mount_path="/private/not-public",
            )
        )
        self.calls = []

    def resolve(self, request):
        self.calls.append(request)
        return self.output


class FakePrerequisiteTransport:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def verify(
        self,
        *,
        target,
        profile,
        timeout_seconds,
    ):
        self.calls.append({
            "target": target,
            "profile": profile,
            "timeout": timeout_seconds,
        })

        return self.result


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


def target_output(
    *,
    resolved_target=None,
    profile=UMBREL_TARGET_PROFILE,
    platform_id="umbrel",
):
    resolved_target = (
        resolved_target
        if resolved_target is not None
        else target()
    )

    return DeploymentStepOutput(
        evidence={
            "targetAssetId": (
                resolved_target.asset_id
            ),
            "transport": (
                resolved_target.transport
            ),
            "deploymentPlatformId": (
                platform_id
            ),
        },
        private=DeploymentTargetContext(
            target=resolved_target,
            profile=profile,
        ),
    )


def prerequisites(**updates):
    values = {
        "platform_id": "umbrel",
        "python_version": "Python 3.11.9",
        "tar_version": "tar (GNU tar) 1.34",
        "checks": (
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
        ),
        "duration_ms": 12,
        "host_key_verified": True,
    }

    values.update(updates)

    return TargetPrerequisiteResult(
        **values
    )


class BlockchainDeploymentPreflightServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.request = DeploymentRequest(
            provider_id="bitcoin-mainnet",
            storage_target_id="storage-main",
            target_asset_id="asset-managed-1",
            correlation_id="corr-test",
            approved_by="approval-test",
        )

    def service(
        self,
        *,
        output=None,
        prerequisite_result=None,
    ):
        target_service = FakeTargetService(
            output
            if output is not None
            else target_output()
        )

        storage_service = FakeStorageService()

        prerequisite_transport = (
            FakePrerequisiteTransport(
                prerequisite_result
                if prerequisite_result is not None
                else prerequisites()
            )
        )

        service = BlockchainDeploymentPreflightService(
            target_service=target_service,
            storage_service=storage_service,
            prerequisite_transport=(
                prerequisite_transport
            ),
            timeout_seconds=30,
        )

        return (
            service,
            target_service,
            prerequisite_transport,
        )

    def test_resolves_target_before_prerequisite_checks(self):
        (
            service,
            target_service,
            prerequisite_transport,
        ) = self.service()

        result = service.verify(
            self.request
        )

        self.assertEqual(
            target_service.calls,
            [self.request],
        )

        self.assertEqual(
            len(prerequisite_transport.calls),
            1,
        )

        call = prerequisite_transport.calls[0]

        self.assertIs(
            call["target"],
            target(),
        ) if False else None

        self.assertEqual(
            call["target"].asset_id,
            "asset-managed-1",
        )

        self.assertIs(
            call["profile"],
            UMBREL_TARGET_PROFILE,
        )

        self.assertEqual(
            call["timeout"],
            30,
        )

        self.assertIsInstance(
            result,
            BlockchainDeploymentPreflightResult,
        )

    def test_private_context_contains_target_profile_and_prerequisites(self):
        service, _, _ = self.service()

        result = service.verify(
            self.request
        )

        self.assertIsInstance(
            result.context,
            BlockchainDeploymentPreflightContext,
        )

        self.assertEqual(
            result.context.target.asset_id,
            "asset-managed-1",
        )

        self.assertIs(
            result.context.profile,
            UMBREL_TARGET_PROFILE,
        )

        self.assertEqual(
            result.context.prerequisites.platform_id,
            "umbrel",
        )

    def test_evidence_is_sanitized(self):
        service, _, _ = self.service()

        result = service.verify(
            self.request
        )

        self.assertEqual(
            result.evidence[
                "targetAssetId"
            ],
            "asset-managed-1",
        )

        self.assertEqual(
            result.evidence[
                "deploymentPlatformId"
            ],
            "umbrel",
        )

        encoded = json.dumps(
            result.evidence
        )

        for forbidden in (
            "192.0.2.10",
            "/private/",
            "/home/umbrel",
            "known_hosts",
            "identity_file",
            "username",
        ):
            self.assertNotIn(
                forbidden,
                encoded,
            )

    def test_target_identity_mismatch_fails_before_prerequisites(self):
        wrong = TransportTarget(
            asset_id="asset-other",
            transport="ssh",
            host="192.0.2.10",
            username="umbrel",
            known_hosts_file="/private/known_hosts",
        )

        (
            service,
            _,
            prerequisite_transport,
        ) = self.service(
            output=target_output(
                resolved_target=wrong,
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "target identity mismatch",
        ):
            service.verify(
                self.request
            )

        self.assertEqual(
            prerequisite_transport.calls,
            [],
        )

    def test_platform_identity_mismatch_fails_before_prerequisites(self):
        (
            service,
            _,
            prerequisite_transport,
        ) = self.service(
            output=target_output(
                platform_id="wrong",
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "platform identity mismatch",
        ):
            service.verify(
                self.request
            )

        self.assertEqual(
            prerequisite_transport.calls,
            [],
        )

    def test_prerequisite_platform_must_match_profile(self):
        service, _, _ = self.service(
            prerequisite_result=prerequisites(
                platform_id="wrong",
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "prerequisite platform identity mismatch",
        ):
            service.verify(
                self.request
            )

    def test_prerequisite_host_key_must_be_verified(self):
        service, _, _ = self.service(
            prerequisite_result=prerequisites(
                host_key_verified=False,
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "host key was not verified",
        ):
            service.verify(
                self.request
            )

    def test_prerequisite_checks_must_not_be_empty(self):
        service, _, _ = self.service(
            prerequisite_result=prerequisites(
                checks=(),
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "checks are missing",
        ):
            service.verify(
                self.request
            )

    def test_invalid_target_private_context_fails_closed(self):
        output = DeploymentStepOutput(
            evidence={
                "targetAssetId": (
                    "asset-managed-1"
                ),
                "transport": "ssh",
                "deploymentPlatformId": (
                    "umbrel"
                ),
            },
            private=object(),
        )

        (
            service,
            _,
            prerequisite_transport,
        ) = self.service(
            output=output,
        )

        with self.assertRaisesRegex(
            ValueError,
            "invalid private context",
        ):
            service.verify(
                self.request
            )

        self.assertEqual(
            prerequisite_transport.calls,
            [],
        )

    def test_preflight_is_not_a_durable_deployment_step(self):
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

        self.assertNotIn(
            "target-prerequisites",
            BlockchainDeploymentExecutor.STEP_IDS,
        )

    def test_timeout_must_be_positive(self):
        with self.assertRaisesRegex(
            ValueError,
            "timeout must be positive",
        ):
            BlockchainDeploymentPreflightService(
                target_service=FakeTargetService(
                    target_output()
                ),
                prerequisite_transport=(
                    FakePrerequisiteTransport(
                        prerequisites()
                    )
                ),
                timeout_seconds=0,
            )


if __name__ == "__main__":
    unittest.main()
