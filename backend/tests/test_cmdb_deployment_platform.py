from __future__ import annotations

import unittest

from backend.core.asset_manager import normalize_asset
from backend.db.repositories.asset_repository import _row_to_asset


class CmdbDeploymentPlatformTests(unittest.TestCase):
    def test_normalization_preserves_explicit_umbrel(self):
        asset = normalize_asset({
            "id": "asset-1",
            "name": "host-1",
            "ip": "192.0.2.10",
            "assetType": "server",
            "deploymentPlatformId": "umbrel",
        })

        self.assertEqual(
            asset["deploymentPlatformId"],
            "umbrel",
        )

    def test_normalization_blank_remains_blank(self):
        asset = normalize_asset({
            "id": "asset-1",
            "name": "host-1",
            "ip": "192.0.2.10",
            "assetType": "server",
        })

        self.assertEqual(
            asset["deploymentPlatformId"],
            "",
        )

    def test_normalization_does_not_infer_from_linux(self):
        asset = normalize_asset({
            "id": "asset-1",
            "name": "umbrel-host",
            "hostname": "umbrel",
            "ip": "192.0.2.10",
            "assetType": "server",
            "operatingSystem": "Linux",
            "capabilities": [
                "managed-host",
                "blockchain-runtime-host",
            ],
        })

        self.assertEqual(
            asset["deploymentPlatformId"],
            "",
        )

    def test_repository_projection_preserves_platform(self):
        asset = _row_to_asset({
            "asset_id": "asset-1",
            "asset_type": "server",
            "canonical_type": "server",
            "name": "host-1",
            "managed": True,
            "deployment_platform_id": "umbrel",
        })

        self.assertEqual(
            asset["deploymentPlatformId"],
            "umbrel",
        )

    def test_repository_projection_blank_is_blank(self):
        asset = _row_to_asset({
            "asset_id": "asset-1",
            "asset_type": "server",
            "canonical_type": "server",
            "name": "host-1",
            "managed": True,
            "deployment_platform_id": None,
        })

        self.assertEqual(
            asset["deploymentPlatformId"],
            "",
        )


if __name__ == "__main__":
    unittest.main()
