from __future__ import annotations

import unittest
from unittest.mock import patch

from backend.services import change_management_service


class BlockchainInstallProviderCreationValidationTests(
    unittest.TestCase
):
    def test_canonical_bch_provider_is_accepted(self):
        change_management_service._validate_creation_contract(
            {
                "capability": "blockchain.install",
                "parameters": {
                    "providerId": "bitcoin-cash-mainnet",
                    "storageTargetId": "storage-main",
                },
            }
        )

    def test_historical_bch_alias_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "Unknown blockchain provider: bitcoin-cash",
        ):
            change_management_service._validate_creation_contract(
                {
                    "capability": "blockchain.install",
                    "parameters": {
                        "providerId": "bitcoin-cash",
                        "storageTargetId": "storage-main",
                    },
                }
            )

    def test_missing_parameters_are_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "parameters are required",
        ):
            change_management_service._validate_creation_contract(
                {
                    "capability": "blockchain.install",
                }
            )

    def test_non_blockchain_change_is_unchanged(self):
        change_management_service._validate_creation_contract(
            {
                "capability": "service.restart",
                "parameters": {
                    "service": "example.service",
                },
            }
        )

    def test_invalid_provider_rejected_before_persistence(self):
        data = {
            "capability": "blockchain.install",
            "parameters": {
                "providerId": "bitcoin-cash",
                "storageTargetId": "storage-main",
            },
        }

        with patch.object(
            change_management_service.repo,
            "create_change",
        ) as create_change:
            with self.assertRaisesRegex(
                ValueError,
                "Unknown blockchain provider: bitcoin-cash",
            ):
                change_management_service.create(data)

        create_change.assert_not_called()


if __name__ == "__main__":
    unittest.main()
