import unittest

from backend.capabilities.registry import get_capability_registry
from backend.executors.managed_host_executor import ManagedHostExecutor


class BlockchainInstallCapabilityTests(unittest.TestCase):
    def setUp(self):
        self.registry = get_capability_registry()
        self.capability = self.registry.resolve("blockchain.install")

    def test_capability_is_high_risk_and_requires_approval(self):
        self.assertEqual(self.capability.risk_level, "high")
        self.assertTrue(self.capability.requires_approval)
        self.assertEqual(
            self.capability.allowed_parameters,
            frozenset({"providerId", "storageTargetId"}),
        )

    def test_executor_allow_lists_capability(self):
        self.assertIn(
            "blockchain.install",
            ManagedHostExecutor.ACTIONS,
        )

    def test_unknown_parameter_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "Unsupported parameters",
        ):
            self.registry.validate_parameters(
                self.capability,
                {
                    "providerId": "bitcoin-mainnet",
                    "storageTargetId": "storage-1",
                    "command": "anything",
                },
            )

    def test_missing_provider_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "providerId",
        ):
            self.registry.validate_parameters(
                self.capability,
                {"storageTargetId": "storage-1"},
            )

    def test_missing_storage_target_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "storageTargetId",
        ):
            self.registry.validate_parameters(
                self.capability,
                {"providerId": "bitcoin-mainnet"},
            )

    def test_valid_contract_fails_closed_until_adapter_enabled(self):
        with self.assertRaisesRegex(
            ValueError,
            "execution adapter is not enabled",
        ):
            self.registry.validate_parameters(
                self.capability,
                {
                    "providerId": "bitcoin-mainnet",
                    "storageTargetId": "storage-1",
                },
            )


if __name__ == "__main__":
    unittest.main()
