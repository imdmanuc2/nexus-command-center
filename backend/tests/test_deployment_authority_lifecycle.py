import unittest

from backend.services.deployment_authority_management_service import (
    DeploymentAuthorityManagementService,
)
from backend.services.blockchain_deployment_target_service import (
    BlockchainDeploymentTargetService,
)
from backend.services.blockchain_deployment_storage_service import (
    BlockchainDeploymentStorageService,
)
from backend.services.blockchain_target_platform import (
    UMBREL_TARGET_PROFILE,
)
from backend.transports.models import (
    TransportTarget,
)


HOST_ID = "asset-host-lifecycle"
STORAGE_ID = "asset-storage-lifecycle"


class AuthorityLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.assets = {
            HOST_ID: {
                "id": HOST_ID,
                "assetType": "server",
                "canonicalType": "server",
                "name": "umbrel-test",
                "managed": True,
                "deploymentPlatformId": "",
                "capabilities": [
                    "managed-host",
                    "blockchain-runtime-host",
                ],
                "metadata": {
                    "preserve": "yes",
                },
            }
        }

        self.relationships = []

        self.discovery_candidate = {
            "candidateId": STORAGE_ID,
            "assetId": STORAGE_ID,
            "assetType": "network-storage",
            "canonicalType": "network-storage",
            "name": "192.0.2.20:/export",
            "friendlyName": "/mnt/seymour-storage",
            "displayName": "/mnt/seymour-storage",
            "primaryRole": "Network Storage",
            "purpose": "Blockchain Storage",
            "managed": True,
            "managementModel": "nexus-managed",
            "hostAssetId": HOST_ID,
            "source": "192.0.2.20:/export",
            "mountPath": "/mnt/seymour-storage",
            "mountPaths": [
                "/mnt/seymour-storage",
            ],
            "filesystem": "nfs4",
            "networkStorage": True,
            "mount": {},
            "approvalRequired": True,
            "approved": False,
        }

    def asset_getter(self, asset_id):
        asset = self.assets.get(asset_id)

        if asset is None:
            return None

        return dict(asset)

    def cmdb_asset_getter(self, asset_id):
        asset = self.assets.get(asset_id)

        if asset is None:
            return {
                "status": "not-found",
                "source": "offline-lifecycle-cmdb",
                "asset": None,
            }

        return {
            "status": "ok",
            "source": "offline-lifecycle-cmdb",
            "asset": dict(asset),
        }

    def asset_writer(self, payload):
        clean = {
            key: value
            for key, value in payload.items()
            if not key.startswith("_")
        }

        self.assets[clean["id"]] = dict(clean)

        return dict(clean)

    def candidate_provider(self, host_asset):
        return [
            dict(self.discovery_candidate)
        ]

    def storage_enroller(
        self,
        candidate,
        *,
        actor_id,
        execute=False,
    ):
        if not execute:
            return {
                "status": "planned",
                "executable": True,
                "asset": {
                    "id": candidate["assetId"],
                },
                "relationship": {
                    "sourceId": candidate["hostAssetId"],
                    "relationshipType": "mounts",
                    "targetId": candidate["assetId"],
                },
            }

        storage_asset = {
            "id": candidate["assetId"],
            "assetType": "network-storage",
            "canonicalType": "network-storage",
            "name": candidate["name"],
            "managed": True,
            "capabilities": [
                "blockchain-storage",
                "network-storage",
            ],
            "metadata": {
                "mountPath": candidate["mountPath"],
                "filesystem": candidate["filesystem"],
            },
        }

        self.assets[STORAGE_ID] = storage_asset

        relationship = {
            "relationshipId": "relationship-lifecycle",
            "sourceType": "asset",
            "sourceId": HOST_ID,
            "relationshipType": "mounts",
            "targetType": "asset",
            "targetId": STORAGE_ID,
            "status": "active",
            "approved": True,
            "observed": True,
            "confidence": 100,
            "source": "managed-host-storage-enrollment",
            "metadata": {
                "mountPath": "/mnt/seymour-storage",
                "filesystem": "nfs4",
            },
        }

        self.relationships = [
            relationship
        ]

        return {
            "status": "enrolled",
            "executable": True,
            "asset": dict(storage_asset),
            "relationship": dict(relationship),
        }

    def relationship_revoker(self, **kwargs):
        execute = bool(
            kwargs.get("execute")
        )

        if not execute:
            return {
                "status": "planned",
                "executable": True,
                "executionPerformed": False,
            }

        matches = [
            item
            for item in self.relationships
            if item["sourceType"] == kwargs["source_type"]
            and item["sourceId"] == kwargs["source_id"]
            and item["relationshipType"] == kwargs["relationship_type"]
            and item["targetType"] == kwargs["target_type"]
            and item["targetId"] == kwargs["target_id"]
            and item["status"] == "active"
            and item["approved"] is True
        ]

        if len(matches) != 1:
            raise ValueError(
                "Relationship revocation requires one active approved relationship."
            )

        relationship = matches[0]
        relationship["status"] = "inactive"
        relationship["approved"] = False

        return {
            "status": "revoked",
            "executable": True,
            "executionPerformed": True,
            "relationshipId": relationship["relationshipId"],
            "relationshipStatus": "inactive",
            "approved": False,
        }

    def active_relationships(self):
        return [
            dict(item)
            for item in self.relationships
            if item["status"] == "active"
            and item["approved"] is True
        ]

    def platform_resolver(self, platform_id):
        if platform_id != "umbrel":
            raise ValueError(
                "Unsupported platform."
            )

        return UMBREL_TARGET_PROFILE

    def target_resolver(self, payload):
        self.assertEqual(
            payload,
            {
                "entityId": HOST_ID,
                "inputPayload": {
                    "assetId": HOST_ID,
                    "transport": "ssh",
                },
            },
        )

        return TransportTarget(
            asset_id=HOST_ID,
            transport="ssh",
            host="192.0.2.10",
            port=22,
            username="umbrel",
            identity_file="/private/identity",
            known_hosts_file="/private/known_hosts",
        )

    def test_full_grant_revoke_authority_lifecycle(self):
        authority = DeploymentAuthorityManagementService(
            asset_getter=self.asset_getter,
            asset_writer=self.asset_writer,
            storage_candidate_provider=self.candidate_provider,
            storage_enroller=self.storage_enroller,
            platform_resolver=self.platform_resolver,
            relationship_revoker=self.relationship_revoker,
        )

        target_service = BlockchainDeploymentTargetService(
            asset_getter=self.cmdb_asset_getter,
            target_resolver=self.target_resolver,
            platform_resolver=self.platform_resolver,
        )

        storage_service = BlockchainDeploymentStorageService(
            asset_getter=self.cmdb_asset_getter,
            relationship_getter=self.active_relationships,
        )

        request = type(
            "Request",
            (),
            {
                "provider_id": "bitcoin-mainnet",
                "target_asset_id": HOST_ID,
                "storage_target_id": STORAGE_ID,
                "correlation_id": "corr-lifecycle",
                "approved_by": "operator-test",
            },
        )()

        #
        # 1. Blank platform classification must fail closed.
        #
        with self.assertRaises(ValueError):
            target_service.resolve(
                request
            )

        #
        # 2. Explicit platform grant.
        #
        platform_result = (
            authority.classify_deployment_platform(
                asset_id=HOST_ID,
                platform_id="umbrel",
                actor_id="operator-test",
                execute=True,
            )
        )

        self.assertEqual(
            platform_result["status"],
            "classified",
        )
        self.assertTrue(
            platform_result["executionPerformed"]
        )

        self.assertEqual(
            self.assets[HOST_ID]["deploymentPlatformId"],
            "umbrel",
        )

        #
        # 3. Target authority must now resolve.
        #
        target_context = target_service.resolve(
            request
        )

        self.assertEqual(
            target_context.evidence,
            {
                "targetAssetId": HOST_ID,
                "transport": "ssh",
                "deploymentPlatformId": "umbrel",
            },
        )

        self.assertIsNotNone(
            target_context.private
        )

        self.assertEqual(
            target_context.private.profile.platform_id,
            "umbrel",
        )

        self.assertEqual(
            target_context.private.target.asset_id,
            HOST_ID,
        )

        self.assertEqual(
            target_context.private.target.transport,
            "ssh",
        )

        #
        # 4. Storage must still fail before grant.
        #
        with self.assertRaises(ValueError):
            storage_service.resolve(
                request
            )

        #
        # 5. Explicit storage grant.
        #
        storage_result = authority.enroll_storage(
            asset_id=HOST_ID,
            storage_asset_id=STORAGE_ID,
            actor_id="operator-test",
            approved=True,
            execute=True,
        )

        self.assertEqual(
            storage_result["status"],
            "enrolled",
        )
        self.assertTrue(
            storage_result["executionPerformed"]
        )

        self.assertIn(
            STORAGE_ID,
            self.assets,
        )

        self.assertEqual(
            len(self.active_relationships()),
            1,
        )

        #
        # 6. Storage deployment authority must resolve.
        #
        storage_context = storage_service.resolve(
            request
        )

        self.assertEqual(
            storage_context.storage_asset_id,
            STORAGE_ID,
        )

        self.assertEqual(
            storage_context.target_asset_id,
            HOST_ID,
        )

        #
        # 7. Revoke storage authority.
        #
        revoke_storage = (
            authority.revoke_storage_authority(
                asset_id=HOST_ID,
                storage_asset_id=STORAGE_ID,
                actor_id="operator-test",
                execute=True,
            )
        )

        self.assertEqual(
            revoke_storage["status"],
            "revoked",
        )
        self.assertTrue(
            revoke_storage["executionPerformed"]
        )

        self.assertIn(
            STORAGE_ID,
            self.assets,
        )

        self.assertEqual(
            self.active_relationships(),
            [],
        )

        #
        # 8. Storage authority must immediately fail closed.
        #
        with self.assertRaises(ValueError):
            storage_service.resolve(
                request
            )

        #
        # 9. Re-grant same storage authority.
        #
        storage_restore = authority.enroll_storage(
            asset_id=HOST_ID,
            storage_asset_id=STORAGE_ID,
            actor_id="operator-test",
            approved=True,
            execute=True,
        )

        self.assertEqual(
            storage_restore["status"],
            "enrolled",
        )

        restored_storage = storage_service.resolve(
            request
        )

        self.assertEqual(
            restored_storage.storage_asset_id,
            STORAGE_ID,
        )

        #
        # 10. Revoke platform authority.
        #
        revoke_platform = (
            authority.revoke_deployment_platform(
                asset_id=HOST_ID,
                actor_id="operator-test",
                execute=True,
            )
        )

        self.assertEqual(
            revoke_platform["status"],
            "revoked",
        )

        self.assertEqual(
            self.assets[HOST_ID]["deploymentPlatformId"],
            "",
        )

        #
        # 11. Target authority must immediately fail closed.
        #
        with self.assertRaises(ValueError):
            target_service.resolve(
                request
            )


if __name__ == "__main__":
    unittest.main()
