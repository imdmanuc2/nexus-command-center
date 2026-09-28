import unittest

from backend.services.deployment_authority_management_service import (
    DeploymentAuthorityManagementService,
)


def managed_host(platform="umbrel"):
    return {
        "id": "asset-host-1",
        "assetType": "server",
        "canonicalType": "server",
        "name": "host-1",
        "managed": True,
        "deploymentPlatformId": platform,
        "capabilities": [
            "managed-host",
            "blockchain-runtime-host",
        ],
        "metadata": {
            "preserve": "yes",
        },
    }


class DeploymentAuthorityRevocationTests(
    unittest.TestCase
):
    def test_platform_revoke_plan_does_not_write(self):
        writes = []

        service = DeploymentAuthorityManagementService(
            asset_getter=lambda asset_id: managed_host(),
            asset_writer=lambda payload: (
                writes.append(payload)
                or payload
            ),
        )

        result = (
            service.revoke_deployment_platform(
                asset_id="asset-host-1",
                actor_id="operator-1",
                execute=False,
            )
        )

        self.assertEqual(
            result["status"],
            "planned",
        )
        self.assertFalse(
            result["executionPerformed"]
        )
        self.assertEqual(
            result["previousPlatformId"],
            "umbrel",
        )
        self.assertEqual(
            result["deploymentPlatformId"],
            "",
        )
        self.assertEqual(
            writes,
            [],
        )

    def test_platform_revoke_requires_existing_authority(self):
        service = DeploymentAuthorityManagementService(
            asset_getter=lambda asset_id: (
                managed_host("")
            ),
        )

        with self.assertRaises(
            ValueError
        ):
            service.revoke_deployment_platform(
                asset_id="asset-host-1",
                actor_id="operator-1",
                execute=False,
            )

    def test_platform_revoke_execute_preserves_asset(self):
        writes = []

        def writer(payload):
            writes.append(
                dict(payload)
            )

            return {
                key: value
                for key, value
                in payload.items()
                if not key.startswith("_")
            }

        service = DeploymentAuthorityManagementService(
            asset_getter=lambda asset_id: managed_host(),
            asset_writer=writer,
        )

        result = (
            service.revoke_deployment_platform(
                asset_id="asset-host-1",
                actor_id="operator-1",
                execute=True,
            )
        )

        self.assertEqual(
            result["status"],
            "revoked",
        )
        self.assertTrue(
            result["executionPerformed"]
        )
        self.assertEqual(
            len(writes),
            1,
        )
        self.assertEqual(
            writes[0]["deploymentPlatformId"],
            "",
        )
        self.assertEqual(
            writes[0]["metadata"],
            {"preserve": "yes"},
        )
        self.assertEqual(
            writes[0]["_actorType"],
            "user",
        )
        self.assertEqual(
            writes[0]["_actorId"],
            "operator-1",
        )

    def test_storage_revoke_plan_delegates_exact_identity(self):
        calls = []

        def revoker(**kwargs):
            calls.append(
                dict(kwargs)
            )

            return {
                "status": "planned",
                "executable": True,
                "executionPerformed": False,
            }

        service = DeploymentAuthorityManagementService(
            asset_getter=lambda asset_id: managed_host(),
            relationship_revoker=revoker,
        )

        result = (
            service.revoke_storage_authority(
                asset_id="asset-host-1",
                storage_asset_id="asset-storage-1",
                actor_id="operator-1",
                execute=False,
            )
        )

        self.assertEqual(
            result["status"],
            "planned",
        )
        self.assertFalse(
            result["executionPerformed"]
        )
        self.assertEqual(
            len(calls),
            1,
        )

        call = calls[0]

        self.assertEqual(
            call["source_type"],
            "asset",
        )
        self.assertEqual(
            call["source_id"],
            "asset-host-1",
        )
        self.assertEqual(
            call["relationship_type"],
            "mounts",
        )
        self.assertEqual(
            call["target_type"],
            "asset",
        )
        self.assertEqual(
            call["target_id"],
            "asset-storage-1",
        )
        self.assertEqual(
            call["actor_id"],
            "operator-1",
        )
        self.assertFalse(
            call["execute"]
        )

    def test_storage_revoke_execute_is_explicit(self):
        calls = []

        def revoker(**kwargs):
            calls.append(
                dict(kwargs)
            )

            return {
                "status": "revoked",
                "executable": True,
                "executionPerformed": True,
                "relationshipStatus": "inactive",
                "approved": False,
            }

        service = DeploymentAuthorityManagementService(
            asset_getter=lambda asset_id: managed_host(),
            relationship_revoker=revoker,
        )

        result = (
            service.revoke_storage_authority(
                asset_id="asset-host-1",
                storage_asset_id="asset-storage-1",
                actor_id="operator-1",
                execute=True,
            )
        )

        self.assertEqual(
            result["status"],
            "revoked",
        )
        self.assertTrue(
            result["executionPerformed"]
        )
        self.assertEqual(
            result["relationshipStatus"],
            "inactive",
        )
        self.assertFalse(
            result["approved"]
        )
        self.assertTrue(
            calls[0]["execute"]
        )

    def test_storage_revoke_requires_storage_identity(self):
        service = DeploymentAuthorityManagementService(
            asset_getter=lambda asset_id: managed_host(),
            relationship_revoker=lambda **kwargs: {},
        )

        with self.assertRaises(
            ValueError
        ):
            service.revoke_storage_authority(
                asset_id="asset-host-1",
                storage_asset_id="",
                actor_id="operator-1",
            )


if __name__ == "__main__":
    unittest.main()
