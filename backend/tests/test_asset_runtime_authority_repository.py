from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
REPOSITORY = (
    ROOT
    / "backend"
    / "db"
    / "repositories"
    / "asset_repository.py"
)


class AssetRuntimeAuthorityRepositoryTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.text = REPOSITORY.read_text()

    def test_runtime_lookup_is_exact_provider_metadata_query(self):
        self.assertIn(
            "metadata->>'providerId' = %s",
            self.text,
        )

        self.assertIn(
            "asset_type = 'blockchain-node'",
            self.text,
        )

        self.assertIn(
            "metadata->>'appId'",
            self.text,
        )

    def test_metadata_merge_is_exact_asset_id_jsonb_merge(self):
        self.assertIn(
            "COALESCE(metadata, '{}'::jsonb)",
            self.text,
        )

        self.assertIn(
            "WHERE asset_id = %s",
            self.text,
        )

        self.assertIn(
            "Jsonb(metadata)",
            self.text,
        )

    def test_metadata_merge_returns_confirmation(self):
        self.assertIn(
            "RETURNING asset_id, metadata, updated_at",
            self.text,
        )


if __name__ == "__main__":
    unittest.main()
