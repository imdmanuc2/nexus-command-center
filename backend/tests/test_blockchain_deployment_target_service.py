from __future__ import annotations

import json
import unittest
from unittest.mock import Mock

from backend.executors.blockchain_deployment_executor import (
    DeploymentRequest,
)
from backend.services.blockchain_deployment_target_service import (
    BlockchainDeploymentTargetService,
    DeploymentTargetContext,
)
from backend.services.blockchain_target_platform import (
    TargetPlatformProfile,
    UMBREL_TARGET_PROFILE,
)
from backend.transports.models import TransportTarget


class BlockchainDeploymentTargetServiceTests(
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

        self.asset = {
            "id": "asset-managed-1",
            "managed": True,
            "lifecycleStatus": "managed",
            "ip": "192.0.2.10",
            "managementModel": "nexus-managed",
            "deploymentPlatformId": "umbrel",
        }

        self.asset_getter = Mock(
            return_value={
                "status": "ok",
                "source": "nexus-postgresql-cmdb",
                "asset": self.asset,
            }
        )

        self.target = TransportTarget(
            asset_id="asset-managed-1",
            transport="ssh",
            host="192.0.2.10",
            port=22,
            username="umbrel",
            identity_file="/private/identity",
            known_hosts_file="/private/known_hosts",
        )

        self.target_resolver = Mock(
            return_value=self.target
        )

        self.platform_resolver = Mock(
            return_value=UMBREL_TARGET_PROFILE
        )

        self.service = BlockchainDeploymentTargetService(
            asset_getter=self.asset_getter,
            target_resolver=self.target_resolver,
            platform_resolver=self.platform_resolver,
        )

    def test_cmdb_checked_before_platform_and_target_resolution(self):
        output = self.service.resolve(
            self.request
        )

        self.asset_getter.assert_called_once_with(
            "asset-managed-1"
        )

        self.platform_resolver.assert_called_once_with(
            "umbrel"
        )

        self.target_resolver.assert_called_once()

        self.assertIsInstance(
            output.private,
            DeploymentTargetContext,
        )

    def test_explicit_cmdb_platform_is_required(self):
        self.asset["deploymentPlatformId"] = ""

        with self.assertRaisesRegex(
            ValueError,
            "no explicit deployment platform classification",
        ):
            self.service.resolve(
                self.request
            )

        self.platform_resolver.assert_not_called()
        self.target_resolver.assert_not_called()

    def test_missing_platform_field_is_not_inferred(self):
        self.asset.pop(
            "deploymentPlatformId"
        )

        self.asset["hostname"] = "umbrel"
        self.asset["operatingSystem"] = "Linux"
        self.asset["capabilities"] = [
            "managed-host",
            "blockchain-runtime-host",
        ]

        with self.assertRaisesRegex(
            ValueError,
            "no explicit deployment platform classification",
        ):
            self.service.resolve(
                self.request
            )

        self.platform_resolver.assert_not_called()
        self.target_resolver.assert_not_called()

    def test_unsupported_platform_fails_before_target_resolution(self):
        self.asset[
            "deploymentPlatformId"
        ] = "standalone-linux"

        self.platform_resolver.side_effect = ValueError(
            "Unsupported target platform: standalone-linux"
        )

        with self.assertRaisesRegex(
            ValueError,
            "Unsupported target platform",
        ):
            self.service.resolve(
                self.request
            )

        self.platform_resolver.assert_called_once_with(
            "standalone-linux"
        )
        self.target_resolver.assert_not_called()

    def test_platform_profile_identity_must_match_cmdb(self):
        wrong = TargetPlatformProfile(
            platform_id="wrong",
            staging_root="/tmp/stage",
            runtime_root="/tmp/runtime",
            lifecycle_adapter_id="wrong",
            test_path="/usr/bin/test",
            python3_path="/usr/bin/python3",
            tar_path="/usr/bin/tar",
            sha256sum_path="/usr/bin/sha256sum",
            rm_path="/usr/bin/rm",
        )

        self.platform_resolver.return_value = wrong

        with self.assertRaisesRegex(
            ValueError,
            "profile identity mismatch",
        ):
            self.service.resolve(
                self.request
            )

        self.target_resolver.assert_not_called()

    def test_invalid_platform_profile_fails_before_target_resolution(self):
        self.platform_resolver.return_value = object()

        with self.assertRaisesRegex(
            ValueError,
            "invalid profile",
        ):
            self.service.resolve(
                self.request
            )

        self.target_resolver.assert_not_called()

    def test_resolver_is_forced_to_ssh(self):
        self.service.resolve(
            self.request
        )

        run = (
            self.target_resolver
            .call_args.args[0]
        )

        self.assertEqual(
            run,
            {
                "entityId": "asset-managed-1",
                "inputPayload": {
                    "assetId": "asset-managed-1",
                    "transport": "ssh",
                },
            },
        )

    def test_evidence_contains_only_safe_platform_identity(self):
        output = self.service.resolve(
            self.request
        )

        self.assertEqual(
            output.evidence,
            {
                "targetAssetId": "asset-managed-1",
                "transport": "ssh",
                "deploymentPlatformId": "umbrel",
            },
        )

        encoded = json.dumps(
            output.evidence
        )

        self.assertNotIn(
            "192.0.2.10",
            encoded,
        )
        self.assertNotIn(
            "/private/identity",
            encoded,
        )
        self.assertNotIn(
            "/private/known_hosts",
            encoded,
        )
        self.assertNotIn(
            "/home/umbrel",
            encoded,
        )

    def test_target_and_profile_remain_private(self):
        output = self.service.resolve(
            self.request
        )

        self.assertIsInstance(
            output.private,
            DeploymentTargetContext,
        )

        self.assertIs(
            output.private.target,
            self.target,
        )

        self.assertIs(
            output.private.profile,
            UMBREL_TARGET_PROFILE,
        )

        self.assertEqual(
            output.private.target.known_hosts_file,
            "/private/known_hosts",
        )

    def test_missing_cmdb_asset_fails_before_resolvers(self):
        self.asset_getter.return_value = {
            "status": "not-found",
            "source": "nexus-postgresql-cmdb",
            "asset": None,
        }

        with self.assertRaisesRegex(
            ValueError,
            "does not exist in CMDB",
        ):
            self.service.resolve(
                self.request
            )

        self.platform_resolver.assert_not_called()
        self.target_resolver.assert_not_called()

    def test_unmanaged_cmdb_asset_fails_before_resolvers(self):
        self.asset["managed"] = False

        with self.assertRaisesRegex(
            ValueError,
            "not Nexus-managed",
        ):
            self.service.resolve(
                self.request
            )

        self.platform_resolver.assert_not_called()
        self.target_resolver.assert_not_called()

    def test_cmdb_identity_mismatch_fails_before_resolvers(self):
        self.asset["id"] = "asset-other"

        with self.assertRaisesRegex(
            ValueError,
            "identity mismatch",
        ):
            self.service.resolve(
                self.request
            )

        self.platform_resolver.assert_not_called()
        self.target_resolver.assert_not_called()

    def test_resolved_target_identity_must_match_cmdb(self):
        self.target_resolver.return_value = (
            TransportTarget(
                asset_id="asset-other",
                transport="ssh",
                host="192.0.2.10",
                username="umbrel",
                identity_file="/private/identity",
                known_hosts_file="/private/known_hosts",
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "transport target identity mismatch",
        ):
            self.service.resolve(
                self.request
            )

    def test_non_ssh_resolved_target_is_rejected(self):
        self.target_resolver.return_value = (
            TransportTarget(
                asset_id="asset-managed-1",
                transport="local",
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "requires SSH transport",
        ):
            self.service.resolve(
                self.request
            )

    def test_missing_host_is_rejected(self):
        self.target_resolver.return_value = (
            TransportTarget(
                asset_id="asset-managed-1",
                transport="ssh",
                host="",
                username="umbrel",
                known_hosts_file="/private/known_hosts",
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "SSH host is missing",
        ):
            self.service.resolve(
                self.request
            )

    def test_missing_username_is_rejected(self):
        self.target_resolver.return_value = (
            TransportTarget(
                asset_id="asset-managed-1",
                transport="ssh",
                host="192.0.2.10",
                username="",
                known_hosts_file="/private/known_hosts",
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "SSH username is missing",
        ):
            self.service.resolve(
                self.request
            )

    def test_missing_known_hosts_is_rejected(self):
        self.target_resolver.return_value = (
            TransportTarget(
                asset_id="asset-managed-1",
                transport="ssh",
                host="192.0.2.10",
                username="umbrel",
                known_hosts_file="",
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "known-hosts file is missing",
        ):
            self.service.resolve(
                self.request
            )


if __name__ == "__main__":
    unittest.main()
