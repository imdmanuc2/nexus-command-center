import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.project_blockchain_provider_catalog import (
    project_catalog,
)


class BlockchainProviderCatalogProjectionTest(unittest.TestCase):
    def test_projection_contract(self):
        canonical = {
            "providers": [
                {
                    "providerId": "bitcoin-mainnet",
                    "ticker": "BTC",
                    "displayName": "Bitcoin",
                    "family": "bitcoin",
                    "network": "mainnet",
                    "implementation": "Bitcoin Core",
                    "availability": "live",
                    "selectable": True,
                    "supportedArchitectures": [
                        "amd64",
                        "arm64",
                    ],
                    "defaultPorts": {
                        "rpc": 8332,
                        "p2p": 8333,
                    },
                    "estimatedDiskBytes": 800000000000,
                },
                {
                    "providerId": "dash-mainnet",
                    "ticker": "DASH",
                    "displayName": "Dash",
                    "family": "bitcoin",
                    "network": "mainnet",
                    "implementation": "Dash Core",
                    "availability": "planned",
                    "selectable": False,
                    "supportedArchitectures": [
                        "amd64",
                        "arm64",
                    ],
                    "defaultPorts": {
                        "rpc": 9998,
                        "p2p": 9999,
                    },
                    "estimatedDiskBytes": 150000000000,
                },
                {
                    "providerId": "ergo-mainnet",
                    "ticker": "ERG",
                    "displayName": "Ergo",
                    "family": "extended-utxo",
                    "network": "mainnet",
                    "implementation": "Ergo Node",
                    "availability": "coming-soon",
                    "selectable": False,
                    "supportedArchitectures": [
                        "amd64",
                        "arm64",
                    ],
                    "defaultPorts": {
                        "restApi": 9053,
                        "p2p": 9030,
                    },
                    "estimatedDiskBytes": 100000000000,
                },
                {
                    "providerId": "ethereum-classic-mainnet",
                    "ticker": "ETC",
                    "displayName": "Ethereum Classic",
                    "family": "ethereum",
                    "network": "mainnet",
                    "implementation": "Core-Geth",
                    "availability": "coming-soon",
                    "selectable": False,
                },
            ]
        }

        projected = project_catalog(canonical)

        self.assertEqual(
            projected["schemaVersion"],
            1,
        )

        providers = projected["providers"]

        # Product-state grouping:
        # live -> coming-soon -> planned.
        self.assertEqual(
            [
                p["providerId"]
                for p in providers
            ],
            [
                "bitcoin-mainnet",
                "ergo-mainnet",
                "ethereum-classic-mainnet",
                "dash-mainnet",
            ],
        )

        by_id = {
            p["providerId"]: p
            for p in providers
        }

        btc = by_id["bitcoin-mainnet"]

        self.assertTrue(btc["enabled"])
        self.assertTrue(btc["selectable"])

        self.assertEqual(
            btc["defaultPorts"],
            {
                "p2p": 8333,
                "rpc": 8332,
            },
        )

        self.assertEqual(
            btc["storage"],
            {
                "directoryName": "bitcoin-mainnet",
                "minimumFreeBytes": 800000000000,
            },
        )

        ergo = by_id["ergo-mainnet"]

        self.assertTrue(ergo["enabled"])
        self.assertFalse(ergo["selectable"])

        self.assertEqual(
            ergo["defaultPorts"],
            {
                "p2p": 9030,
                "rpc": 9053,
            },
        )

        etc = by_id["ethereum-classic-mainnet"]

        self.assertTrue(etc["enabled"])
        self.assertFalse(etc["selectable"])
        self.assertEqual(etc["architectures"], [])
        self.assertEqual(etc["defaultPorts"], {})

        self.assertEqual(
            etc["storage"],
            {
                "directoryName": "ethereum-classic-mainnet",
                "minimumFreeBytes": None,
            },
        )


if __name__ == "__main__":
    unittest.main()
