from backend.db.repositories.maintenance_repository import VALID_TARGET_TYPES


def test_target_catalog():
    assert {"asset", "asset_type", "site", "rack", "pool", "cluster", "tag"} == VALID_TARGET_TYPES
