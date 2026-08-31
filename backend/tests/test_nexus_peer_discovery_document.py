import unittest
from unittest.mock import patch

from backend.core import discovery
from backend.services import nexus_peer_discovery_service


class NexusPeerDiscoveryDocumentTests(
    unittest.TestCase
):
    def valid_payload(self):
        return {
            "status": "ok",
            "service": "nexus-command-center",
            "discoveryVersion": "1",
            "instance": {
                "instanceId": "nexus-test1234",
                "name": "Test Nexus",
                "hostname": "test-host",
            },
            "peerProtocol": {
                "name": "seymour-nexus-peer",
                "version": "1",
            },
            "machineIdentity": {
                "algorithm": "Ed25519",
                "publicKey": (
                    "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
                    "AAAAAAAAAAA"
                ),
                "fingerprint": (
                    "sha256:66687aadf862bd776c8fc18b"
                    "8e9f8e20089714856ee233b3902a591d0d5f2925"
                ),
            },
        }

    def test_valid_nexus_discovery_document(self):
        self.assertTrue(
            discovery._valid_nexus_discovery_document(
                self.valid_payload()
            )
        )

    def test_rejects_wrong_service(self):
        payload = self.valid_payload()
        payload["service"] = "something-else"

        self.assertFalse(
            discovery._valid_nexus_discovery_document(
                payload
            )
        )

    def test_rejects_public_key_fingerprint_mismatch(self):
        payload = self.valid_payload()

        payload["machineIdentity"]["fingerprint"] = (
            "sha256:"
            + ("0" * 64)
        )

        self.assertFalse(
            discovery._valid_nexus_discovery_document(
                payload
            )
        )

    def test_rejects_invalid_public_key(self):
        payload = self.valid_payload()

        payload["machineIdentity"]["publicKey"] = (
            "not-a-valid-ed25519-key"
        )

        self.assertFalse(
            discovery._valid_nexus_discovery_document(
                payload
            )
        )

    def test_rejects_wrong_protocol(self):
        payload = self.valid_payload()
        payload["peerProtocol"]["name"] = "wrong"

        self.assertFalse(
            discovery._valid_nexus_discovery_document(
                payload
            )
        )

    def test_discovery_disabled(self):
        with patch.object(
            nexus_peer_discovery_service,
            "discovery_enabled",
            return_value=False,
        ):
            with self.assertRaises(PermissionError):
                (
                    nexus_peer_discovery_service
                    .discovery_document()
                )

    def test_discovery_document_public_fields(self):
        identity = {
            "organizationId": "org-private",
            "organizationName": "Private Org",
            "siteId": "site-private",
            "siteName": "Private Site",
            "instanceId": "nexus-test1234",
            "instanceName": "Test Nexus",
            "hostname": "test-host",
            "identitySource": "test",
        }

        machine = {
            "algorithm": "Ed25519",
            "publicKey": "public-key",
            "fingerprint": "sha256:test",
        }

        with patch.object(
            nexus_peer_discovery_service,
            "discovery_enabled",
            return_value=True,
        ), patch.object(
            nexus_peer_discovery_service,
            "runtime_identity",
            return_value=identity,
        ), patch.object(
            nexus_peer_discovery_service
            .nexus_peer_machine_identity_service,
            "local_public_identity",
            return_value=machine,
        ):
            payload = (
                nexus_peer_discovery_service
                .discovery_document()
            )

        self.assertEqual(
            payload["instance"],
            {
                "instanceId": "nexus-test1234",
                "name": "Test Nexus",
                "hostname": "test-host",
            },
        )

        serialized = str(payload)

        self.assertNotIn("org-private", serialized)
        self.assertNotIn("Private Org", serialized)
        self.assertNotIn("site-private", serialized)
        self.assertNotIn("Private Site", serialized)

    def test_settings_gate_uses_existing_contract(self):
        with patch.object(
            nexus_peer_discovery_service
            .nexus_peer_settings_service,
            "get_settings",
            return_value={
                "status": "ok",
                "settings": {
                    "localDiscoveryEnabled": True,
                },
            },
        ):
            self.assertTrue(
                nexus_peer_discovery_service
                .discovery_enabled()
            )

        with patch.object(
            nexus_peer_discovery_service
            .nexus_peer_settings_service,
            "get_settings",
            return_value={
                "status": "ok",
                "settings": {
                    "localDiscoveryEnabled": False,
                },
            },
        ):
            self.assertFalse(
                nexus_peer_discovery_service
                .discovery_enabled()
            )


if __name__ == "__main__":
    unittest.main()
