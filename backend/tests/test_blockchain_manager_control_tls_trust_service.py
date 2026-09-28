from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
import ssl
import tempfile
import unittest

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

from backend.services.blockchain_manager_control_tls_trust_service import (
    create_ssl_context,
    load_ca_file,
    trust_path,
)


def _test_ca_certificate() -> str:
    """Create a valid ephemeral test-only CA certificate.

    The private key exists only in memory for certificate signing and
    is discarded immediately. No private key is written to the repo or
    filesystem.
    """

    private_key = (
        ec.generate_private_key(
            ec.SECP256R1()
        )
    )

    subject = issuer = x509.Name([
        x509.NameAttribute(
            NameOID.COMMON_NAME,
            "Seymour Blockchain Manager Unit Test CA",
        ),
    ])

    now = datetime.now(
        UTC
    )

    certificate = (
        x509.CertificateBuilder()
        .subject_name(
            subject
        )
        .issuer_name(
            issuer
        )
        .public_key(
            private_key.public_key()
        )
        .serial_number(
            x509.random_serial_number()
        )
        .not_valid_before(
            now - timedelta(minutes=1)
        )
        .not_valid_after(
            now + timedelta(days=1)
        )
        .add_extension(
            x509.BasicConstraints(
                ca=True,
                path_length=None,
            ),
            critical=True,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=True,
                crl_sign=True,
                encipher_only=None,
                decipher_only=None,
            ),
            critical=True,
        )
        .sign(
            private_key=private_key,
            algorithm=hashes.SHA256(),
        )
    )

    return (
        certificate.public_bytes(
            serialization.Encoding.PEM
        )
        .decode("ascii")
    )


class BlockchainManagerControlTlsTrustTests(
    unittest.TestCase
):
    def make_directory(self):
        temp = tempfile.TemporaryDirectory()

        root = Path(
            temp.name
        )

        root.chmod(
            0o700
        )

        return temp, root

    def write_ca(
        self,
        root: Path,
        target: str = "asset-154",
        content: str | None = None,
    ):
        path = trust_path(
            target,
            directory=root,
        )

        if content is None:
            content = (
                _test_ca_certificate()
            )

        path.write_text(
            content,
            encoding="utf-8",
        )

        path.chmod(
            0o600
        )

        return path

    def test_target_bound_path(self):
        temp, root = self.make_directory()

        try:
            self.assertEqual(
                trust_path(
                    "asset-154",
                    directory=root,
                ),
                root / "asset-154.ca.pem",
            )
        finally:
            temp.cleanup()

    def test_rejects_target_traversal(self):
        temp, root = self.make_directory()

        try:
            with self.assertRaisesRegex(
                ValueError,
                "Invalid .* target",
            ):
                trust_path(
                    "../asset-154",
                    directory=root,
                )
        finally:
            temp.cleanup()

    def test_missing_trust_fails_closed(self):
        temp, root = self.make_directory()

        try:
            with self.assertRaisesRegex(
                ValueError,
                "trust is missing",
            ):
                load_ca_file(
                    target_asset_id="asset-154",
                    directory=root,
                )
        finally:
            temp.cleanup()

    def test_insecure_directory_fails_closed(self):
        temp, root = self.make_directory()

        try:
            root.chmod(
                0o755
            )

            with self.assertRaisesRegex(
                ValueError,
                "directory permissions",
            ):
                load_ca_file(
                    target_asset_id="asset-154",
                    directory=root,
                )
        finally:
            temp.cleanup()

    def test_insecure_file_fails_closed(self):
        temp, root = self.make_directory()

        try:
            path = self.write_ca(
                root
            )

            path.chmod(
                0o644
            )

            with self.assertRaisesRegex(
                ValueError,
                "file permissions",
            ):
                load_ca_file(
                    target_asset_id="asset-154",
                    directory=root,
                )
        finally:
            temp.cleanup()

    def test_non_pem_file_fails_closed(self):
        temp, root = self.make_directory()

        try:
            self.write_ca(
                root,
                content="not a certificate\n",
            )

            with self.assertRaisesRegex(
                ValueError,
                "PEM certificate",
            ):
                load_ca_file(
                    target_asset_id="asset-154",
                    directory=root,
                )
        finally:
            temp.cleanup()

    def test_loads_exact_target_ca_file(self):
        temp, root = self.make_directory()

        try:
            expected = self.write_ca(
                root
            )

            result = load_ca_file(
                target_asset_id="asset-154",
                directory=root,
            )

            self.assertEqual(
                result,
                expected,
            )
        finally:
            temp.cleanup()

    def test_builds_verified_server_auth_context(self):
        temp, root = self.make_directory()

        try:
            self.write_ca(
                root
            )

            context = create_ssl_context(
                target_asset_id="asset-154",
                directory=root,
            )

            self.assertIsInstance(
                context,
                ssl.SSLContext,
            )

            self.assertTrue(
                context.check_hostname
            )

            self.assertEqual(
                context.verify_mode,
                ssl.CERT_REQUIRED,
            )
        finally:
            temp.cleanup()


if __name__ == "__main__":
    unittest.main()
