from __future__ import annotations

import copy
import unittest

from backend.services.blockchain_runtime_authority_projection_service import (
    BlockchainRuntimeAuthorityProjectionError,
    BlockchainRuntimeAuthorityProjectionService,
)


PROVIDER = "bitcoin-cash-mainnet"
RUNTIME = "asset-runtime-bch"
HOST = "asset-host-156"
STORAGE = "asset-storage-156"


def runtime(**metadata_updates):
    metadata = {
        "appId": "seymour-bch-node",
        "providerId": PROVIDER,
        "source": "seymour-blockchain-manager",
        "network": "mainnet",
        "preserveMe": "yes",
    }
    metadata.update(metadata_updates)

    return {
        "assetId": RUNTIME,
        "assetType": "blockchain-node",
        "metadata": metadata,
    }


class Store:
    def __init__(self, runtimes):
        self.runtimes = copy.deepcopy(runtimes)
        self.writes = []

    def find(self, provider_id):
        return [
            copy.deepcopy(value)
            for value in self.runtimes
            if (
                value.get("metadata", {}).get("providerId")
                == provider_id
            )
        ]

    def merge(self, asset_id, patch):
        self.writes.append(
            (
                asset_id,
                copy.deepcopy(patch),
            )
        )

        for value in self.runtimes:
            if value["assetId"] == asset_id:
                value["metadata"].update(
                    copy.deepcopy(patch)
                )

                return {
                    "assetId": asset_id,
                    "metadata": copy.deepcopy(
                        value["metadata"]
                    ),
                }

        raise KeyError(asset_id)


class ProjectionTests(unittest.TestCase):

    def service(self, store):
        return BlockchainRuntimeAuthorityProjectionService(
            runtime_finder=store.find,
            metadata_merger=store.merge,
        )

    def test_projects_exact_authority(self):
        store = Store([runtime()])

        result = self.service(store).project(
            provider_id=PROVIDER,
            target_asset_id=HOST,
            storage_target_id=STORAGE,
        )

        self.assertEqual(
            result.runtime_asset_id,
            RUNTIME,
        )

        metadata = store.runtimes[0]["metadata"]

        self.assertEqual(
            metadata["hostAssetId"],
            HOST,
        )
        self.assertEqual(
            metadata["storageAssetId"],
            STORAGE,
        )
        self.assertEqual(
            metadata["providerId"],
            PROVIDER,
        )
        self.assertEqual(
            metadata["preserveMe"],
            "yes",
        )

    def test_exact_patch_only(self):
        store = Store([runtime()])

        self.service(store).project(
            provider_id=PROVIDER,
            target_asset_id=HOST,
            storage_target_id=STORAGE,
        )

        self.assertEqual(
            store.writes,
            [
                (
                    RUNTIME,
                    {
                        "providerId": PROVIDER,
                        "hostAssetId": HOST,
                        "storageAssetId": STORAGE,
                    },
                )
            ],
        )

    def test_idempotent_existing_authority(self):
        store = Store([
            runtime(
                hostAssetId=HOST,
                storageAssetId=STORAGE,
            )
        ])

        service = self.service(store)

        first = service.project(
            provider_id=PROVIDER,
            target_asset_id=HOST,
            storage_target_id=STORAGE,
        )

        second = service.project(
            provider_id=PROVIDER,
            target_asset_id=HOST,
            storage_target_id=STORAGE,
        )

        self.assertEqual(first, second)
        self.assertEqual(store.writes, [])

    def test_conflicting_host_fails_closed(self):
        store = Store([
            runtime(
                hostAssetId="asset-other-host",
            )
        ])

        with self.assertRaises(
            BlockchainRuntimeAuthorityProjectionError
        ):
            self.service(store).project(
                provider_id=PROVIDER,
                target_asset_id=HOST,
                storage_target_id=STORAGE,
            )

        self.assertEqual(store.writes, [])

    def test_conflicting_storage_fails_closed(self):
        store = Store([
            runtime(
                storageAssetId="asset-other-storage",
            )
        ])

        with self.assertRaises(
            BlockchainRuntimeAuthorityProjectionError
        ):
            self.service(store).project(
                provider_id=PROVIDER,
                target_asset_id=HOST,
                storage_target_id=STORAGE,
            )

        self.assertEqual(store.writes, [])

    def test_missing_runtime_fails_closed(self):
        store = Store([])

        with self.assertRaises(
            BlockchainRuntimeAuthorityProjectionError
        ):
            self.service(store).project(
                provider_id=PROVIDER,
                target_asset_id=HOST,
                storage_target_id=STORAGE,
            )

        self.assertEqual(store.writes, [])

    def test_ambiguous_runtime_fails_closed(self):
        first = runtime()
        second = runtime()
        second["assetId"] = "asset-runtime-two"
        second["metadata"]["appId"] = "second-bch-runtime"

        store = Store([first, second])

        with self.assertRaises(
            BlockchainRuntimeAuthorityProjectionError
        ):
            self.service(store).project(
                provider_id=PROVIDER,
                target_asset_id=HOST,
                storage_target_id=STORAGE,
            )

        self.assertEqual(store.writes, [])

    def test_missing_app_identity_fails_closed(self):
        value = runtime()
        value["metadata"]["appId"] = ""

        store = Store([value])

        with self.assertRaises(
            BlockchainRuntimeAuthorityProjectionError
        ):
            self.service(store).project(
                provider_id=PROVIDER,
                target_asset_id=HOST,
                storage_target_id=STORAGE,
            )

        self.assertEqual(store.writes, [])


if __name__ == "__main__":
    unittest.main()
