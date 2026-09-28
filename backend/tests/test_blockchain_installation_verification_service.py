from __future__ import annotations

import unittest

from backend.executors.blockchain_deployment_executor import (
    DeploymentRequest,
)
from backend.services.blockchain_installation_verification_service import (
    BlockchainInstallationVerificationService,
    InstallationVerificationContext,
)
from backend.services.blockchain_installer_invocation_service import (
    BlockchainInstallerInvocationContext,
)
from backend.transports.installation_verification import (
    INSTALLATION_CONTRACT,
    INSTALLATION_CONTRACT_VERSION,
    InstallationVerificationResult,
)
from backend.transports.models import TransportTarget


class FakeInstallationVerificationTransport:
    def __init__(self, result):
        self.result = result
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

        return self.result


def installer_context(**updates):
    values = {
        "provider_id": "bitcoin-mainnet",
        "storage_target_id": "storage-main",
        "operation_id": "op-test-install",
        "success": True,
    }
    values.update(updates)

    return BlockchainInstallerInvocationContext(
        **values
    )


def good_result(**updates):
    values = {
        "contract": INSTALLATION_CONTRACT,
        "contract_version": (
            INSTALLATION_CONTRACT_VERSION
        ),
        "operation_id": "op-test-install",
        "provider_id": "bitcoin-mainnet",
        "storage_target_id": "storage-main",
        "status": "installed",
        "verified": True,
        "state_verified": True,
        "runtime_data_mount_matches": True,
        "runtime_blocks_mount_matches": True,
        "binding_mode": "single-path",
        "recorded_at": (
            "2026-09-10T00:00:00+00:00"
        ),
        "duration_ms": 9,
        "host_key_verified": True,
    }
    values.update(updates)

    return InstallationVerificationResult(
        **values
    )


class BlockchainInstallationVerificationServiceTests(
    unittest.TestCase
):
    def setUp(self):
        self.target = TransportTarget(
            asset_id="asset-1",
            transport="ssh",
            host="192.0.2.10",
            port=22,
            username="umbrel",
            identity_file="/private/key",
            known_hosts_file="/private/known_hosts",
        )

        self.request = DeploymentRequest(
            provider_id="bitcoin-mainnet",
            storage_target_id="storage-main",
            target_asset_id="asset-1",
            correlation_id="corr-1",
            approved_by="operator",
        )

    def private(self, installer=None):
        return {
            "invoke-installer": (
                installer
                if installer is not None
                else installer_context()
            ),
        }

    def service(self, result=None):
        fake = FakeInstallationVerificationTransport(
            result or good_result()
        )

        service = BlockchainInstallationVerificationService(
            target=self.target,
            transport=fake,
            timeout_seconds=30,
        )

        return service, fake

    def test_queries_only_requested_provider(self):
        service, fake = self.service()

        output = service.execute(
            request=self.request,
            private=self.private(),
        )

        typed = fake.calls[0]["request"]

        self.assertEqual(
            set(
                typed.__dataclass_fields__
            ),
            {"provider_id"},
        )
        self.assertEqual(
            typed.provider_id,
            "bitcoin-mainnet",
        )
        self.assertEqual(
            output.evidence["operationId"],
            "op-test-install",
        )

    def test_requires_installer_context(self):
        service, fake = self.service()

        with self.assertRaisesRegex(
            ValueError,
            "invoke-installer",
        ):
            service.execute(
                request=self.request,
                private={},
            )

        self.assertEqual(fake.calls, [])

    def test_installer_provider_mismatch_fails_before_transport(self):
        service, fake = self.service()

        with self.assertRaisesRegex(
            ValueError,
            "Installer provider",
        ):
            service.execute(
                request=self.request,
                private=self.private(
                    installer_context(
                        provider_id="wrong-provider"
                    )
                ),
            )

        self.assertEqual(fake.calls, [])

    def test_installer_storage_mismatch_fails_before_transport(self):
        service, fake = self.service()

        with self.assertRaisesRegex(
            ValueError,
            "Installer storage target",
        ):
            service.execute(
                request=self.request,
                private=self.private(
                    installer_context(
                        storage_target_id="wrong"
                    )
                ),
            )

        self.assertEqual(fake.calls, [])

    def test_missing_installer_operation_id_fails_before_transport(self):
        service, fake = self.service()

        with self.assertRaisesRegex(
            ValueError,
            "operation ID is missing",
        ):
            service.execute(
                request=self.request,
                private=self.private(
                    installer_context(
                        operation_id=""
                    )
                ),
            )

        self.assertEqual(fake.calls, [])

    def test_unsuccessful_installer_fails_before_transport(self):
        service, fake = self.service()

        with self.assertRaisesRegex(
            ValueError,
            "does not indicate success",
        ):
            service.execute(
                request=self.request,
                private=self.private(
                    installer_context(
                        success=False
                    )
                ),
            )

        self.assertEqual(fake.calls, [])

    def test_exact_operation_id_is_required(self):
        service, _ = self.service(
            good_result(
                operation_id="different-operation"
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "operation ID does not match",
        ):
            service.execute(
                request=self.request,
                private=self.private(),
            )

    def test_exact_provider_is_required(self):
        service, _ = self.service(
            good_result(
                provider_id="wrong-provider"
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "provider does not match",
        ):
            service.execute(
                request=self.request,
                private=self.private(),
            )

    def test_exact_storage_target_is_required(self):
        service, _ = self.service(
            good_result(
                storage_target_id="wrong-storage"
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "storage target does not match",
        ):
            service.execute(
                request=self.request,
                private=self.private(),
            )

    def test_all_verification_assertions_are_required(self):
        cases = (
            ("verified", "is not verified"),
            (
                "state_verified",
                "state is not verified",
            ),
            (
                "runtime_data_mount_matches",
                "data mount does not match",
            ),
            (
                "runtime_blocks_mount_matches",
                "blocks mount does not match",
            ),
        )

        for field, message in cases:
            with self.subTest(field=field):
                service, _ = self.service(
                    good_result(
                        **{field: False}
                    )
                )

                with self.assertRaisesRegex(
                    ValueError,
                    message,
                ):
                    service.execute(
                        request=self.request,
                        private=self.private(),
                    )

    def test_target_asset_mismatch_fails_before_transport(self):
        request = DeploymentRequest(
            provider_id="bitcoin-mainnet",
            storage_target_id="storage-main",
            target_asset_id="asset-2",
            correlation_id="corr-1",
            approved_by="operator",
        )

        service, fake = self.service()

        with self.assertRaisesRegex(
            ValueError,
            "target does not match",
        ):
            service.execute(
                request=request,
                private=self.private(),
            )

        self.assertEqual(fake.calls, [])

    def test_host_key_failure_fails_closed(self):
        service, _ = self.service(
            good_result(
                host_key_verified=False
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "did not verify host key",
        ):
            service.execute(
                request=self.request,
                private=self.private(),
            )

    def test_durable_evidence_is_provider_install_evidence(self):
        service, _ = self.service()

        output = service.execute(
            request=self.request,
            private=self.private(),
        )

        self.assertEqual(
            output.evidence,
            {
                "contract": INSTALLATION_CONTRACT,
                "contractVersion": 1,
                "operationId": "op-test-install",
                "providerId": "bitcoin-mainnet",
                "storageTargetId": "storage-main",
                "status": "installed",
                "verified": True,
                "stateVerified": True,
                "runtimeDataMountMatches": True,
                "runtimeBlocksMountMatches": True,
                "bindingMode": "single-path",
                "recordedAt": (
                    "2026-09-10T00:00:00+00:00"
                ),
                "durationMs": 9,
                "hostKeyVerified": True,
            },
        )

        encoded = repr(output.evidence)

        self.assertNotIn(
            "runtimeVersion",
            encoded,
        )
        self.assertNotIn(
            "sourceRevision",
            encoded,
        )
        self.assertNotIn(
            "payloadManifestSha256",
            encoded,
        )
        self.assertNotIn(
            "/home/umbrel",
            encoded,
        )
        self.assertNotIn(
            "/private/",
            encoded,
        )

    def test_private_context_is_typed(self):
        service, _ = self.service()

        output = service.execute(
            request=self.request,
            private=self.private(),
        )

        self.assertIsInstance(
            output.private,
            InstallationVerificationContext,
        )

        self.assertEqual(
            output.private.operation_id,
            "op-test-install",
        )


if __name__ == "__main__":
    unittest.main()
