import unittest

from backend.core.asset_manager import normalize_asset


class AssetManagerStorageNormalizationTests(unittest.TestCase):
    def test_network_storage_does_not_require_ip(self):
        result = normalize_asset(
            {
                "id": "asset-storage-network-1",
                "assetType": "network-storage",
                "canonicalType": "network-storage",
                "name": "192.0.2.10:/exports/blockchain",
                "friendlyName": "/mnt/blockchain",
                "managed": True,
                "managementModel": "nexus-managed",
                "primaryRole": "Network Storage",
                "purpose": "Blockchain Storage",
                "capabilities": [
                    "blockchain-storage",
                    "network-storage",
                ],
            }
        )

        self.assertEqual(
            result.get("assetType"),
            "network-storage",
        )
        self.assertEqual(
            result.get("canonicalType"),
            "network-storage",
        )
        self.assertEqual(
            result.get("ip"),
            "",
        )

    def test_local_storage_does_not_require_ip(self):
        result = normalize_asset(
            {
                "id": "asset-storage-local-1",
                "assetType": "storage",
                "canonicalType": "storage",
                "name": "/dev/sdb1",
                "friendlyName": "/mnt/storage",
                "managed": True,
                "managementModel": "nexus-managed",
                "primaryRole": "Host Storage",
                "purpose": "Blockchain Storage",
                "capabilities": [
                    "blockchain-storage",
                ],
            }
        )

        self.assertEqual(
            result.get("assetType"),
            "storage",
        )
        self.assertEqual(
            result.get("canonicalType"),
            "storage",
        )
        self.assertEqual(
            result.get("ip"),
            "",
        )

    def test_server_still_requires_ip(self):
        with self.assertRaisesRegex(
            ValueError,
            "Infrastructure asset requires an IP address",
        ):
            normalize_asset(
                {
                    "id": "asset-host-no-ip",
                    "assetType": "server",
                    "canonicalType": "server",
                    "name": "host-without-ip",
                    "managed": True,
                }
            )

    def test_unknown_asset_still_requires_ip(self):
        with self.assertRaisesRegex(
            ValueError,
            "Infrastructure asset requires an IP address",
        ):
            normalize_asset(
                {
                    "id": "asset-unknown-no-ip",
                    "name": "unknown-without-ip",
                    "managed": True,
                }
            )


if __name__ == "__main__":
    unittest.main()
