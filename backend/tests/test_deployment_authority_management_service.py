from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from backend.services.blockchain_target_platform import (
    UMBREL_TARGET_PROFILE,
)
from backend.services.deployment_authority_management_service import (
    DeploymentAuthorityManagementService,
)


HOST_ID = "asset-host-test-001"
STORAGE_ID = "asset-storage-test-001"


def managed_host(**overrides):
    return {
        "id": HOST_ID,
        "assetType": "server",
        "canonicalType": "server",
        "name": "managed-host",
        "friendlyName": "Managed Host",
        "managed": True,
        "deploymentPlatformId": "",
        "capabilities": [
            "managed-host",
            "blockchain-runtime-host",
        ],
        "observedState": {},
        **overrides,
    }


def storage_candidate():
    return {
        "assetId": STORAGE_ID,
        "hostAssetId": HOST_ID,
        "assetType": "storage",
        "canonicalType": "storage",
        "name": "/mnt/blockchain",
        "mountPath": "/mnt/blockchain",
        "mountPaths": ["/mnt/blockchain"],
        "source": "/dev/sdb1",
        "filesystem": "ext4",
        "networkStorage": False,
        "approved": False,
    }


class DeploymentAuthorityManagementServiceTests(
    unittest.TestCase
):

    def test_missing_asset_fails_closed(self):
        service = DeploymentAuthorityManagementService(
            asset_getter=MagicMock(return_value=None),
        )

        with self.assertRaisesRegex(
            ValueError,
            "canonical CMDB asset",
        ):
            service.classify_deployment_platform(
                asset_id=HOST_ID,
                platform_id="umbrel",
                actor_id="operator",
            )

    def test_unmanaged_asset_fails_closed(self):
        service = DeploymentAuthorityManagementService(
            asset_getter=MagicMock(
                return_value=managed_host(
                    managed=False,
                )
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "managed CMDB asset",
        ):
            service.classify_deployment_platform(
                asset_id=HOST_ID,
                platform_id="umbrel",
                actor_id="operator",
            )

    def test_platform_is_never_inferred(self):
        resolver = MagicMock(
            return_value=UMBREL_TARGET_PROFILE
        )

        service = DeploymentAuthorityManagementService(
            asset_getter=MagicMock(
                return_value=managed_host()
            ),
            platform_resolver=resolver,
        )

        with self.assertRaisesRegex(
            ValueError,
            "platform is required",
        ):
            service.classify_deployment_platform(
                asset_id=HOST_ID,
                platform_id="",
                actor_id="operator",
            )

        resolver.assert_not_called()

    def test_unsupported_platform_fails_before_write(self):
        writer = MagicMock()

        def reject_platform(platform_id):
            raise ValueError(
                f"Unsupported target platform: {platform_id}"
            )

        service = DeploymentAuthorityManagementService(
            asset_getter=MagicMock(
                return_value=managed_host()
            ),
            asset_writer=writer,
            platform_resolver=reject_platform,
        )

        with self.assertRaisesRegex(
            ValueError,
            "Unsupported target platform",
        ):
            service.classify_deployment_platform(
                asset_id=HOST_ID,
                platform_id="debian",
                actor_id="operator",
                execute=True,
            )

        writer.assert_not_called()

    def test_platform_plan_does_not_write(self):
        writer = MagicMock()

        service = DeploymentAuthorityManagementService(
            asset_getter=MagicMock(
                return_value=managed_host()
            ),
            asset_writer=writer,
            platform_resolver=MagicMock(
                return_value=UMBREL_TARGET_PROFILE
            ),
        )

        result = service.classify_deployment_platform(
            asset_id=HOST_ID,
            platform_id="umbrel",
            actor_id="operator-1",
            execute=False,
        )

        self.assertEqual(
            result["status"],
            "planned",
        )
        self.assertTrue(
            result["executable"]
        )
        self.assertFalse(
            result["executionPerformed"]
        )
        self.assertEqual(
            result["deploymentPlatformId"],
            "umbrel",
        )
        self.assertEqual(
            result["asset"]["deploymentPlatformId"],
            "umbrel",
        )
        self.assertEqual(
            result["asset"]["_actorType"],
            "user",
        )
        self.assertEqual(
            result["asset"]["_actorId"],
            "operator-1",
        )

        writer.assert_not_called()

    def test_platform_execute_preserves_asset_and_writes_once(self):
        original = managed_host(
            notes="keep-me",
            observedState={
                "managedHostDiscovery": {
                    "storage": {
                        "mounts": [],
                    }
                }
            },
        )

        writer = MagicMock(
            side_effect=lambda payload: {
                key: value
                for key, value in payload.items()
                if not key.startswith("_")
            }
        )

        service = DeploymentAuthorityManagementService(
            asset_getter=MagicMock(
                return_value=original
            ),
            asset_writer=writer,
            platform_resolver=MagicMock(
                return_value=UMBREL_TARGET_PROFILE
            ),
        )

        result = service.classify_deployment_platform(
            asset_id=HOST_ID,
            platform_id="umbrel",
            actor_id="operator-1",
            execute=True,
        )

        self.assertEqual(
            result["status"],
            "classified",
        )
        self.assertTrue(
            result["executionPerformed"]
        )
        self.assertEqual(
            result["deploymentPlatformId"],
            "umbrel",
        )
        self.assertEqual(
            result["asset"]["id"],
            HOST_ID,
        )
        self.assertEqual(
            result["asset"]["notes"],
            "keep-me",
        )
        self.assertEqual(
            result["asset"]["observedState"],
            original["observedState"],
        )

        writer.assert_called_once()

        payload = writer.call_args.args[0]

        self.assertEqual(
            payload["id"],
            HOST_ID,
        )
        self.assertEqual(
            payload["deploymentPlatformId"],
            "umbrel",
        )
        self.assertEqual(
            payload["_actorType"],
            "user",
        )
        self.assertEqual(
            payload["_actorId"],
            "operator-1",
        )
        self.assertEqual(
            payload["_source"],
            "deployment-authority-management",
        )

    def test_storage_candidates_are_discovery_only(self):
        provider = MagicMock(
            return_value=[
                storage_candidate()
            ]
        )
        enroller = MagicMock()

        service = DeploymentAuthorityManagementService(
            asset_getter=MagicMock(
                return_value=managed_host()
            ),
            storage_candidate_provider=provider,
            storage_enroller=enroller,
        )

        result = service.list_storage_candidates(
            asset_id=HOST_ID,
        )

        self.assertEqual(
            result["status"],
            "ok",
        )
        self.assertEqual(
            result["candidateCount"],
            1,
        )
        self.assertFalse(
            result["executionPerformed"]
        )
        self.assertFalse(
            result["candidates"][0]["approved"]
        )

        enroller.assert_not_called()

    def test_storage_requires_explicit_approval(self):
        provider = MagicMock(
            return_value=[
                storage_candidate()
            ]
        )
        enroller = MagicMock()

        service = DeploymentAuthorityManagementService(
            asset_getter=MagicMock(
                return_value=managed_host()
            ),
            storage_candidate_provider=provider,
            storage_enroller=enroller,
        )

        result = service.enroll_storage(
            asset_id=HOST_ID,
            storage_asset_id=STORAGE_ID,
            actor_id="operator",
            approved=False,
            execute=True,
        )

        self.assertEqual(
            result["status"],
            "approval-required",
        )
        self.assertFalse(
            result["approved"]
        )
        self.assertFalse(
            result["executionPerformed"]
        )

        provider.assert_not_called()
        enroller.assert_not_called()

    def test_storage_selection_must_match_current_discovery(self):
        provider = MagicMock(
            return_value=[
                storage_candidate()
            ]
        )
        enroller = MagicMock()

        service = DeploymentAuthorityManagementService(
            asset_getter=MagicMock(
                return_value=managed_host()
            ),
            storage_candidate_provider=provider,
            storage_enroller=enroller,
        )

        with self.assertRaisesRegex(
            ValueError,
            "exactly one current discovery candidate",
        ):
            service.enroll_storage(
                asset_id=HOST_ID,
                storage_asset_id="asset-storage-other",
                actor_id="operator",
                approved=True,
                execute=True,
            )

        enroller.assert_not_called()

    def test_storage_plan_passes_only_selected_current_candidate(self):
        candidate = storage_candidate()

        provider = MagicMock(
            return_value=[candidate]
        )

        enroller = MagicMock(
            return_value={
                "status": "planned",
                "executable": True,
                "asset": {
                    "id": STORAGE_ID,
                },
                "relationship": {
                    "sourceId": HOST_ID,
                    "targetId": STORAGE_ID,
                },
            }
        )

        service = DeploymentAuthorityManagementService(
            asset_getter=MagicMock(
                return_value=managed_host()
            ),
            storage_candidate_provider=provider,
            storage_enroller=enroller,
        )

        result = service.enroll_storage(
            asset_id=HOST_ID,
            storage_asset_id=STORAGE_ID,
            actor_id="operator-1",
            approved=True,
            execute=False,
        )

        self.assertEqual(
            result["status"],
            "planned",
        )
        self.assertTrue(
            result["approved"]
        )
        self.assertFalse(
            result["executionPerformed"]
        )

        enroller.assert_called_once()

        call = enroller.call_args

        selected = call.args[0]

        self.assertEqual(
            selected["assetId"],
            STORAGE_ID,
        )
        self.assertEqual(
            selected["hostAssetId"],
            HOST_ID,
        )
        self.assertTrue(
            selected["approved"]
        )

        self.assertEqual(
            call.kwargs["actor_id"],
            "operator-1",
        )
        self.assertFalse(
            call.kwargs["execute"]
        )

    def test_storage_execute_delegates_explicitly(self):
        provider = MagicMock(
            return_value=[
                storage_candidate()
            ]
        )

        enroller = MagicMock(
            return_value={
                "status": "enrolled",
                "executable": True,
                "asset": {
                    "id": STORAGE_ID,
                },
                "relationship": {
                    "sourceId": HOST_ID,
                    "targetId": STORAGE_ID,
                    "approved": True,
                },
            }
        )

        service = DeploymentAuthorityManagementService(
            asset_getter=MagicMock(
                return_value=managed_host()
            ),
            storage_candidate_provider=provider,
            storage_enroller=enroller,
        )

        result = service.enroll_storage(
            asset_id=HOST_ID,
            storage_asset_id=STORAGE_ID,
            actor_id="operator-1",
            approved=True,
            execute=True,
        )

        self.assertEqual(
            result["status"],
            "enrolled",
        )
        self.assertTrue(
            result["approved"]
        )
        self.assertTrue(
            result["executionPerformed"]
        )

        enroller.assert_called_once()

        self.assertTrue(
            enroller.call_args.kwargs["execute"]
        )


if __name__ == "__main__":
    unittest.main()
