from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
)

from backend.services import (
    blockchain_manager_control_credential_service as service,
)


class BlockchainManagerControlCredentialTests(
    unittest.TestCase
):
    def setUp(self):
        self.temp = (
            tempfile.TemporaryDirectory()
        )

        self.root = Path(
            self.temp.name
        )

        self.directory = (
            self.root / "credentials"
        )

        self.machine_key = (
            self.root / "machine.key"
        )

        key = Ed25519PrivateKey.generate()

        raw = key.private_bytes(
            encoding=(
                serialization.Encoding.Raw
            ),
            format=(
                serialization
                .PrivateFormat.Raw
            ),
            encryption_algorithm=(
                serialization
                .NoEncryption()
            ),
        )

        self.machine_key.write_bytes(
            raw
        )

        os.chmod(
            self.machine_key,
            0o600,
        )

        self.key = (
            Ed25519PrivateKey
            .from_private_bytes(raw)
        )

        self.patches = [
            patch.object(
                service.nexus_instance_service,
                "get_local_instance",
                return_value={
                    "instance_id":
                        "nexus-test",
                },
            ),
            patch.object(
                service
                .nexus_peer_machine_identity_service,
                "private_key_path",
                return_value=self.machine_key,
            ),
            patch.object(
                service
                .nexus_peer_machine_identity_service,
                "load_private_key",
                return_value=self.key,
            ),
        ]

        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(
            self.patches
        ):
            item.stop()

        self.temp.cleanup()

    def test_round_trip_is_encrypted_and_owner_only(
        self,
    ):
        secret = (
            "durable-control-secret"
        )

        path = service.store_credential(
            target_asset_id="asset-154",
            control_secret=secret,
            directory=self.directory,
        )

        self.assertEqual(
            self.directory.stat().st_mode
            & 0o777,
            0o700,
        )

        self.assertEqual(
            path.stat().st_mode
            & 0o777,
            0o600,
        )

        document = path.read_text(
            encoding="utf-8"
        )

        self.assertNotIn(
            secret,
            document,
        )

        payload = json.loads(
            document
        )

        self.assertEqual(
            payload["algorithm"],
            "AES-256-GCM",
        )

        self.assertEqual(
            payload["keyDerivation"],
            "HKDF-SHA256",
        )

        self.assertEqual(
            service.load_credential(
                target_asset_id="asset-154",
                directory=self.directory,
            ),
            secret,
        )

    def test_target_binding_fails_closed(self):
        service.store_credential(
            target_asset_id="asset-154",
            control_secret="secret",
            directory=self.directory,
        )

        source = service.credential_path(
            "asset-154",
            directory=self.directory,
        )

        other = service.credential_path(
            "asset-155",
            directory=self.directory,
        )

        other.write_bytes(
            source.read_bytes()
        )

        os.chmod(
            other,
            0o600,
        )

        with self.assertRaisesRegex(
            ValueError,
            "authentication failed",
        ):
            service.load_credential(
                target_asset_id="asset-155",
                directory=self.directory,
            )

    def test_local_instance_binding_fails_closed(
        self,
    ):
        service.store_credential(
            target_asset_id="asset-154",
            control_secret="secret",
            directory=self.directory,
        )

        with patch.object(
            service.nexus_instance_service,
            "get_local_instance",
            return_value={
                "instance_id":
                    "different-nexus",
            },
        ):
            with self.assertRaisesRegex(
                ValueError,
                "authentication failed",
            ):
                service.load_credential(
                    target_asset_id="asset-154",
                    directory=self.directory,
                )

    def test_duplicate_store_does_not_overwrite(
        self,
    ):
        service.store_credential(
            target_asset_id="asset-154",
            control_secret="first",
            directory=self.directory,
        )

        with self.assertRaises(
            FileExistsError
        ):
            service.store_credential(
                target_asset_id="asset-154",
                control_secret="second",
                directory=self.directory,
            )

        self.assertEqual(
            service.load_credential(
                target_asset_id="asset-154",
                directory=self.directory,
            ),
            "first",
        )

    def test_path_escape_is_rejected(self):
        with self.assertRaisesRegex(
            ValueError,
            "targetAssetId is invalid",
        ):
            service.credential_path(
                "../escape",
                directory=self.directory,
            )

    def test_insecure_directory_is_rejected(
        self,
    ):
        self.directory.mkdir(
            mode=0o755
        )

        os.chmod(
            self.directory,
            0o755,
        )

        with self.assertRaises(
            PermissionError
        ):
            service.store_credential(
                target_asset_id="asset-154",
                control_secret="secret",
                directory=self.directory,
            )

    def test_insecure_file_is_rejected(self):
        path = service.store_credential(
            target_asset_id="asset-154",
            control_secret="secret",
            directory=self.directory,
        )

        os.chmod(
            path,
            0o644,
        )

        with self.assertRaises(
            PermissionError
        ):
            service.load_credential(
                target_asset_id="asset-154",
                directory=self.directory,
            )

    def test_tampered_ciphertext_is_rejected(
        self,
    ):
        path = service.store_credential(
            target_asset_id="asset-154",
            control_secret="secret",
            directory=self.directory,
        )

        payload = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

        ciphertext = payload[
            "ciphertext"
        ]

        payload["ciphertext"] = (
            ciphertext[:-1]
            + (
                "A"
                if ciphertext[-1] != "A"
                else "B"
            )
        )

        path.write_text(
            json.dumps(
                payload,
                separators=(",", ":"),
                sort_keys=True,
            ),
            encoding="utf-8",
        )

        os.chmod(
            path,
            0o600,
        )

        with self.assertRaisesRegex(
            ValueError,
            "authentication failed",
        ):
            service.load_credential(
                target_asset_id="asset-154",
                directory=self.directory,
            )

    def test_delete_is_idempotent(self):
        service.store_credential(
            target_asset_id="asset-154",
            control_secret="secret",
            directory=self.directory,
        )

        self.assertTrue(
            service.delete_credential(
                target_asset_id="asset-154",
                directory=self.directory,
            )
        )

        self.assertFalse(
            service.delete_credential(
                target_asset_id="asset-154",
                directory=self.directory,
            )
        )


if __name__ == "__main__":
    unittest.main()
