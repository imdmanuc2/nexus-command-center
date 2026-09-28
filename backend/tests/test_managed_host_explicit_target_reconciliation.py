import unittest
from unittest.mock import patch

from backend.core.reconciliation_engine import (
    reconcile_observation,
)


class ManagedHostExplicitTargetReconciliationTests(
    unittest.TestCase
):
    def setUp(self):
        self.existing = {
            "id": "asset-host-test",
            "assetType": "server",
            "name": "Existing Host",
            "friendlyName": "Existing Host",
            "displayName": "Existing Host",
            "deploymentPlatformId": "linux",
            "managementModel": "nexus-managed",
            "managed": True,
            "lifecycleStatus": "managed",
            "ip": "192.0.2.10",
        }

        self.observation = {
            "identity": {
                "ip": "192.0.2.10",
                "hostname": "live-host",
                "machineUuid": "machine-123",
            },
            "classification": {
                "assetType": "server",
            },
            "raw": {
                "name": "live-host",
                "friendlyName": "live-host",
                "displayName": "live-host",
                "hostname": "live-host",
            },
        }

    @patch(
        "backend.core.reconciliation_engine."
        "upsert_managed_asset"
    )
    @patch(
        "backend.core.reconciliation_engine."
        "get_assets_list"
    )
    @patch(
        "backend.core.reconciliation_engine."
        "append_observation"
    )
    def test_explicit_target_reconciles_existing_asset(
        self,
        append_observation,
        get_assets_list,
        upsert_managed_asset,
    ):
        append_observation.return_value = dict(
            self.observation
        )
        get_assets_list.return_value = [
            dict(self.existing)
        ]

        upsert_managed_asset.side_effect = (
            lambda payload: dict(payload)
        )

        result = reconcile_observation(
            self.observation,
            source="managed-host-discovery",
            observer_id="nexus-managed-host",
            approve_new=False,
            actor_id="test",
            target_asset_id="asset-host-test",
        )

        self.assertEqual(
            result["status"],
            "reconciled",
        )
        self.assertEqual(
            result["decision"],
            "matched-existing",
        )
        self.assertEqual(
            result["asset"]["id"],
            "asset-host-test",
        )

        # Authoritative CMDB classification survives.
        self.assertEqual(
            result["asset"]["deploymentPlatformId"],
            "linux",
        )
        self.assertEqual(
            result["asset"]["managementModel"],
            "nexus-managed",
        )
        self.assertEqual(
            result["asset"]["name"],
            "Existing Host",
        )
        self.assertEqual(
            result["asset"]["friendlyName"],
            "Existing Host",
        )
        self.assertEqual(
            result["asset"]["displayName"],
            "Existing Host",
        )

        # Observed identity enriches the same asset.
        self.assertEqual(
            result["asset"]["hostname"],
            "live-host",
        )
        self.assertEqual(
            result["asset"]["machineUuid"],
            "machine-123",
        )

    @patch(
        "backend.core.reconciliation_engine."
        "upsert_managed_asset"
    )
    @patch(
        "backend.core.reconciliation_engine."
        "find_best_match"
    )
    @patch(
        "backend.core.reconciliation_engine."
        "get_assets_list"
    )
    @patch(
        "backend.core.reconciliation_engine."
        "append_observation"
    )
    def test_new_asset_keeps_discovered_display_identity(
        self,
        append_observation,
        get_assets_list,
        find_best_match,
        upsert_managed_asset,
    ):
        append_observation.return_value = dict(
            self.observation
        )
        get_assets_list.return_value = []

        find_best_match.return_value = {
            "decision": "new",
            "confidence": 100,
            "match": None,
            "candidates": [],
        }

        upsert_managed_asset.side_effect = (
            lambda payload: dict(payload)
        )

        result = reconcile_observation(
            self.observation,
            source="discovery",
            observer_id="test",
            approve_new=True,
            actor_id="test",
        )

        self.assertEqual(
            result["status"],
            "reconciled",
        )
        self.assertEqual(
            result["decision"],
            "created-new",
        )

        asset = result["asset"]

        self.assertEqual(
            asset["name"],
            "live-host",
        )
        self.assertEqual(
            asset["friendlyName"],
            "live-host",
        )
        self.assertEqual(
            asset["displayName"],
            "live-host",
        )
        self.assertEqual(
            asset["hostname"],
            "live-host",
        )


    @patch(
        "backend.core.reconciliation_engine."
        "upsert_managed_asset"
    )
    @patch(
        "backend.core.reconciliation_engine."
        "get_assets_list"
    )
    @patch(
        "backend.core.reconciliation_engine."
        "append_observation"
    )
    def test_missing_explicit_target_fails_closed(
        self,
        append_observation,
        get_assets_list,
        upsert_managed_asset,
    ):
        append_observation.return_value = dict(
            self.observation
        )
        get_assets_list.return_value = [
            dict(self.existing)
        ]

        result = reconcile_observation(
            self.observation,
            source="managed-host-discovery",
            observer_id="nexus-managed-host",
            approve_new=True,
            actor_id="test",
            target_asset_id="asset-does-not-exist",
        )

        self.assertEqual(
            result["status"],
            "review-required",
        )
        self.assertEqual(
            result["decision"],
            "explicit-target-not-found",
        )
        self.assertIsNone(result["asset"])
        upsert_managed_asset.assert_not_called()

    @patch(
        "backend.core.reconciliation_engine."
        "upsert_managed_asset"
    )
    @patch(
        "backend.core.reconciliation_engine."
        "find_best_match"
    )
    @patch(
        "backend.core.reconciliation_engine."
        "get_assets_list"
    )
    @patch(
        "backend.core.reconciliation_engine."
        "append_observation"
    )
    def test_generic_discovery_still_uses_identity_matcher(
        self,
        append_observation,
        get_assets_list,
        find_best_match,
        upsert_managed_asset,
    ):
        append_observation.return_value = dict(
            self.observation
        )
        get_assets_list.return_value = [
            dict(self.existing)
        ]

        find_best_match.return_value = {
            "decision": "conflict",
            "confidence": 40,
            "match": {
                "assetId": "asset-host-test",
            },
            "candidates": [],
        }

        result = reconcile_observation(
            self.observation,
            source="discovery",
            observer_id="test",
            approve_new=False,
            actor_id="test",
        )

        find_best_match.assert_called_once()
        self.assertEqual(
            result["status"],
            "review-required",
        )
        self.assertEqual(
            result["decision"],
            "conflict",
        )
        upsert_managed_asset.assert_not_called()


if __name__ == "__main__":
    unittest.main()
