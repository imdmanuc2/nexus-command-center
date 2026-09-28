from __future__ import annotations

import unittest
from unittest.mock import Mock

from backend.executors.blockchain_deployment_executor import (
    DeploymentRequest,
)
from backend.services.blockchain_deployment_storage_service import (
    BlockchainDeploymentStorageService,
    DeploymentStorageContext,
)


TARGET_ID = "asset-managed-1"
STORAGE_ID = "asset-storage-test-1"


def request(
    *,
    target_id=TARGET_ID,
    storage_id=STORAGE_ID,
):
    return DeploymentRequest(
        provider_id="bitcoin-mainnet",
        storage_target_id=storage_id,
        target_asset_id=target_id,
        correlation_id="corr-test",
        approved_by="approval-test",
    )


def storage_asset(
    *,
    asset_id=STORAGE_ID,
    asset_type="storage",
    managed=True,
    capabilities=None,
):
    if capabilities is None:
        capabilities = [
            "blockchain-storage",
            "local-storage",
        ]

    return {
        "id": asset_id,
        "assetType": asset_type,
        "managed": managed,
        "capabilities": capabilities,
        "observedState": {
            "storage": {
                "source": "/dev/sda6",
                "filesystem": "ext4",
                "mountPath": "/private/not-public",
            }
        },
    }


def mount_relationship(
    *,
    source_id=TARGET_ID,
    target_id=STORAGE_ID,
    status="active",
    approved=True,
):
    return {
        "sourceType": "asset",
        "sourceId": source_id,
        "relationshipType": "mounts",
        "targetType": "asset",
        "targetId": target_id,
        "status": status,
        "approved": approved,
        "metadata": {
            "mountPath": "/private/not-public",
        },
    }


class BlockchainDeploymentStorageServiceTests(
    unittest.TestCase
):
    def service(
        self,
        *,
        asset=None,
        relationships=None,
    ):
        if asset is None:
            asset = storage_asset()

        if relationships is None:
            relationships = [
                mount_relationship()
            ]

        asset_getter = Mock(
            return_value={
                "status": "ok",
                "source": "nexus-postgresql-cmdb",
                "asset": asset,
            }
        )

        relationship_getter = Mock(
            return_value=relationships
        )

        service = BlockchainDeploymentStorageService(
            asset_getter=asset_getter,
            relationship_getter=relationship_getter,
        )

        return (
            service,
            asset_getter,
            relationship_getter,
        )

    def test_resolves_canonical_local_storage(self):
        service, asset_getter, relationship_getter = (
            self.service()
        )

        result = service.resolve(
            request()
        )

        self.assertIsInstance(
            result,
            DeploymentStorageContext,
        )

        self.assertEqual(
            result.storage_asset_id,
            STORAGE_ID,
        )

        self.assertEqual(
            result.storage_asset_type,
            "storage",
        )

        self.assertEqual(
            result.target_asset_id,
            TARGET_ID,
        )

        asset_getter.assert_called_once_with(
            STORAGE_ID
        )

        relationship_getter.assert_called_once_with()

    def test_network_storage_is_supported(self):
        service, _, _ = self.service(
            asset=storage_asset(
                asset_type="network-storage",
                capabilities=[
                    "blockchain-storage",
                    "network-storage",
                ],
            )
        )

        result = service.resolve(
            request()
        )

        self.assertEqual(
            result.storage_asset_type,
            "network-storage",
        )

    def test_missing_storage_asset_fails_closed(self):
        asset_getter = Mock(
            return_value={
                "status": "not-found",
                "asset": None,
            }
        )

        relationship_getter = Mock(
            return_value=[
                mount_relationship()
            ]
        )

        service = BlockchainDeploymentStorageService(
            asset_getter=asset_getter,
            relationship_getter=relationship_getter,
        )

        with self.assertRaisesRegex(
            ValueError,
            "does not exist in CMDB",
        ):
            service.resolve(
                request()
            )

        relationship_getter.assert_not_called()

    def test_storage_identity_mismatch_fails_closed(self):
        service, _, relationship_getter = (
            self.service(
                asset=storage_asset(
                    asset_id="asset-storage-other",
                )
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "identity mismatch",
        ):
            service.resolve(
                request()
            )

        relationship_getter.assert_not_called()

    def test_unmanaged_storage_fails_closed(self):
        service, _, relationship_getter = (
            self.service(
                asset=storage_asset(
                    managed=False,
                )
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "not Nexus-managed",
        ):
            service.resolve(
                request()
            )

        relationship_getter.assert_not_called()

    def test_non_storage_asset_fails_closed(self):
        service, _, relationship_getter = (
            self.service(
                asset=storage_asset(
                    asset_type="server",
                )
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "unsupported asset type",
        ):
            service.resolve(
                request()
            )

        relationship_getter.assert_not_called()

    def test_blockchain_storage_capability_is_required(self):
        service, _, relationship_getter = (
            self.service(
                asset=storage_asset(
                    capabilities=[
                        "local-storage"
                    ],
                )
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "not classified for blockchain storage",
        ):
            service.resolve(
                request()
            )

        relationship_getter.assert_not_called()

    def test_missing_mount_relationship_fails_closed(self):
        service, _, _ = self.service(
            relationships=[]
        )

        with self.assertRaisesRegex(
            ValueError,
            "not authorized for the selected deployment target",
        ):
            service.resolve(
                request()
            )

    def test_mount_relationship_must_match_target_host(self):
        service, _, _ = self.service(
            relationships=[
                mount_relationship(
                    source_id="asset-other-host",
                )
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "not authorized",
        ):
            service.resolve(
                request()
            )

    def test_mount_relationship_must_match_storage(self):
        service, _, _ = self.service(
            relationships=[
                mount_relationship(
                    target_id="asset-storage-other",
                )
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "not authorized",
        ):
            service.resolve(
                request()
            )

    def test_inactive_relationship_fails_closed(self):
        service, _, _ = self.service(
            relationships=[
                mount_relationship(
                    status="inactive",
                )
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "not authorized",
        ):
            service.resolve(
                request()
            )

    def test_unapproved_relationship_fails_closed(self):
        service, _, _ = self.service(
            relationships=[
                mount_relationship(
                    approved=False,
                )
            ]
        )

        with self.assertRaisesRegex(
            ValueError,
            "not authorized",
        ):
            service.resolve(
                request()
            )

    def test_wrong_relationship_type_fails_closed(self):
        relationship = mount_relationship()
        relationship[
            "relationshipType"
        ] = "runs-on"

        service, _, _ = self.service(
            relationships=[relationship]
        )

        with self.assertRaisesRegex(
            ValueError,
            "not authorized",
        ):
            service.resolve(
                request()
            )


if __name__ == "__main__":
    unittest.main()
