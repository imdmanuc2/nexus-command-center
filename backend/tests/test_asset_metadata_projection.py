from backend.db.repositories.asset_repository import _row_to_asset


def _base_row(**updates):
    row = {
        "asset_id": "asset-runtime-1",
        "asset_type": "blockchain-node",
        "name": "Bitcoin Cash",
        "metadata": {},
    }
    row.update(updates)
    return row


def test_row_to_asset_defaults_metadata_to_empty_dict():
    asset = _row_to_asset(_base_row(metadata=None))

    assert asset["metadata"] == {}


def test_row_to_asset_preserves_canonical_runtime_metadata():
    metadata = {
        "appId": "seymour-bch-node",
        "providerId": "bitcoin-cash-mainnet",
        "hostAssetId": "asset-c74ff160",
        "storageAssetId": "asset-storage-d10b97d27b2e8307",
        "preserveMe": "unchanged",
    }

    asset = _row_to_asset(_base_row(metadata=metadata))

    assert asset["metadata"] == metadata
    assert asset["metadata"]["appId"] == "seymour-bch-node"
    assert asset["metadata"]["providerId"] == "bitcoin-cash-mainnet"
    assert asset["metadata"]["hostAssetId"] == "asset-c74ff160"
    assert (
        asset["metadata"]["storageAssetId"]
        == "asset-storage-d10b97d27b2e8307"
    )
    assert asset["metadata"]["preserveMe"] == "unchanged"


def test_row_to_asset_preserves_legacy_projection_with_metadata():
    asset = _row_to_asset(
        _base_row(
            metadata={
                "appId": "seymour-bch-node",
                "legacy": {
                    "hostname": "bch-node",
                    "workerId": "worker-1",
                },
            }
        )
    )

    assert asset["metadata"]["appId"] == "seymour-bch-node"
    assert asset["hostname"] == "bch-node"
    assert asset["workerId"] == "worker-1"
