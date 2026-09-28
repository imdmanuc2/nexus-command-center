from __future__ import annotations

import unittest

from backend.capabilities.registry import (
    get_capability_registry,
    validate_blockchain_install_parameters,
)


class BlockchainInstallParameterValidationTests(
    unittest.TestCase
):
    def test_valid_parameters_validate_without_execution(self):
        validate_blockchain_install_parameters(
            {
                "providerId": "bitcoin-mainnet",
                "storageTargetId": "storage-main",
            }
        )

    def test_missing_provider_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "providerId",
        ):
            validate_blockchain_install_parameters(
                {
                    "storageTargetId": "storage-main",
                }
            )

    def test_invalid_provider_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "providerId",
        ):
            validate_blockchain_install_parameters(
                {
                    "providerId": "../bitcoin",
                    "storageTargetId": "storage-main",
                }
            )

    def test_missing_storage_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "storageTargetId",
        ):
            validate_blockchain_install_parameters(
                {
                    "providerId": "bitcoin-mainnet",
                }
            )

    def test_invalid_storage_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "storageTargetId",
        ):
            validate_blockchain_install_parameters(
                {
                    "providerId": "bitcoin-mainnet",
                    "storageTargetId": "../storage",
                }
            )

    def test_unknown_parameter_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "Unsupported parameters",
        ):
            validate_blockchain_install_parameters(
                {
                    "providerId": "bitcoin-mainnet",
                    "storageTargetId": "storage-main",
                    "command": "whoami",
                }
            )

    def test_build_argv_remains_fail_closed(self):
        registry = get_capability_registry()
        capability = registry.resolve(
            "blockchain.install"
        )

        with self.assertRaisesRegex(
            ValueError,
            "execution adapter is not enabled",
        ):
            capability.build_argv(
                {
                    "providerId": "bitcoin-mainnet",
                    "storageTargetId": "storage-main",
                }
            )

    def test_generic_validation_remains_fail_closed(self):
        registry = get_capability_registry()
        capability = registry.resolve(
            "blockchain.install"
        )

        with self.assertRaisesRegex(
            ValueError,
            "execution adapter is not enabled",
        ):
            registry.validate_parameters(
                capability,
                {
                    "providerId": "bitcoin-mainnet",
                    "storageTargetId": "storage-main",
                },
            )


if __name__ == "__main__":
    unittest.main()
