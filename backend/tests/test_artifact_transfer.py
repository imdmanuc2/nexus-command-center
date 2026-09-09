from __future__ import annotations

import hashlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from backend.transports.artifact_transfer import (
    ArtifactTransferError,
    ArtifactTransferRequest,
    SshArtifactTransport,
)
from backend.transports.models import (
    TransportResult,
    TransportTarget,
)


def result(
    *,
    stdout="",
    exit_code=0,
):
    return TransportResult(
        transport="ssh",
        target_asset_id="asset-test",
        exit_code=exit_code,
        stdout=stdout,
        stderr="",
        duration_ms=1,
        host_key_verified=True,
    )


class ArtifactTransferTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)

        self.identity = root / "identity"
        self.known_hosts = root / "known_hosts"

        self.identity.write_text("test", encoding="utf-8")
        self.known_hosts.write_text("test", encoding="utf-8")

        self.source = root / "runtime.tar"
        self.source.write_bytes(b"reviewed-runtime")

        self.sha = hashlib.sha256(
            self.source.read_bytes()
        ).hexdigest()

        self.target = TransportTarget(
            asset_id="asset-test",
            transport="ssh",
            host="192.0.2.10",
            username="umbrel",
            identity_file=str(self.identity),
            known_hosts_file=str(self.known_hosts),
        )

    def tearDown(self):
        self.temp.cleanup()

    def request(self, **changes):
        values = {
            "artifact_id": "sbp-077-runtime.tar",
            "source": self.source,
            "expected_sha256": self.sha,
        }
        values.update(changes)
        return ArtifactTransferRequest(**values)

    def test_rejects_bad_artifact_id(self):
        transport = SshArtifactTransport()

        with self.assertRaises(ArtifactTransferError):
            transport.transfer(
                target=self.target,
                request=self.request(
                    artifact_id="../../escape"
                ),
                timeout_seconds=60,
            )

    def test_rejects_wrong_local_hash_before_transport(self):
        ssh = Mock()

        transport = SshArtifactTransport(
            ssh_transport=ssh,
        )

        with self.assertRaisesRegex(
            ArtifactTransferError,
            "reviewed SHA-256",
        ):
            transport.transfer(
                target=self.target,
                request=self.request(
                    expected_sha256="0" * 64
                ),
                timeout_seconds=60,
            )

        ssh.execute.assert_not_called()

    def test_scp_uses_strict_security_contract(self):
        ssh = Mock()
        ssh.execute.side_effect = [
            result(),
            result(
                stdout=f"{self.sha}  remote\n"
            ),
        ]

        runner = Mock()
        runner.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="",
            stderr="",
        )

        transfer = SshArtifactTransport(
            ssh_transport=ssh,
            runner=runner,
        )

        outcome = transfer.transfer(
            target=self.target,
            request=self.request(),
            timeout_seconds=60,
        )

        command = runner.call_args.args[0]

        self.assertEqual(command[0], "scp")
        self.assertIn("BatchMode=yes", command)
        self.assertIn("IdentitiesOnly=yes", command)
        self.assertIn(
            "StrictHostKeyChecking=yes",
            command,
        )
        self.assertIn(
            "GlobalKnownHostsFile=/dev/null",
            command,
        )
        self.assertIn(
            "PasswordAuthentication=no",
            command,
        )
        self.assertIn(
            "KbdInteractiveAuthentication=no",
            command,
        )

        self.assertFalse(
            runner.call_args.kwargs["shell"]
        )

        self.assertEqual(
            outcome.sha256,
            self.sha,
        )

    def test_remote_hash_mismatch_fails_closed(self):
        ssh = Mock()
        ssh.execute.side_effect = [
            result(),
            result(
                stdout=f"{'f' * 64}  remote\n"
            ),
        ]

        runner = Mock()
        runner.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="",
            stderr="",
        )

        transfer = SshArtifactTransport(
            ssh_transport=ssh,
            runner=runner,
        )

        with self.assertRaisesRegex(
            ArtifactTransferError,
            "SHA-256 mismatch",
        ):
            transfer.transfer(
                target=self.target,
                request=self.request(),
                timeout_seconds=60,
            )

    def test_remote_path_is_derived_not_supplied(self):
        ssh = Mock()
        ssh.execute.side_effect = [
            result(),
            result(
                stdout=f"{self.sha}  remote\n"
            ),
        ]

        runner = Mock()
        runner.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="",
            stderr="",
        )

        outcome = SshArtifactTransport(
            ssh_transport=ssh,
            runner=runner,
        ).transfer(
            target=self.target,
            request=self.request(
                artifact_id="runtime-abc123.tar"
            ),
            timeout_seconds=60,
        )

        self.assertEqual(
            outcome.remote_path,
            (
                "/home/umbrel/.seymour-artifacts/"
                "runtime-abc123.tar"
            ),
        )

    def test_failed_scp_does_not_verify_remote_hash(self):
        ssh = Mock()
        ssh.execute.return_value = result()

        runner = Mock()
        runner.return_value = subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="",
            stderr="synthetic scp failure",
        )

        transfer = SshArtifactTransport(
            ssh_transport=ssh,
            runner=runner,
        )

        with self.assertRaisesRegex(
            ArtifactTransferError,
            "Artifact transfer failed",
        ):
            transfer.transfer(
                target=self.target,
                request=self.request(),
                timeout_seconds=60,
            )

        self.assertEqual(
            ssh.execute.call_count,
            1,
        )

    def test_missing_known_hosts_fails_before_runner(self):
        target = TransportTarget(
            asset_id="asset-test",
            transport="ssh",
            host="192.0.2.10",
            username="umbrel",
            identity_file=str(self.identity),
            known_hosts_file=str(
                Path(self.temp.name) / "missing-known-hosts"
            ),
        )

        runner = Mock()

        with self.assertRaisesRegex(
            ArtifactTransferError,
            "known_hosts_file does not exist",
        ):
            SshArtifactTransport(
                runner=runner,
            ).transfer(
                target=target,
                request=self.request(),
                timeout_seconds=60,
            )

        runner.assert_not_called()

    def test_missing_identity_fails_before_runner(self):
        target = TransportTarget(
            asset_id="asset-test",
            transport="ssh",
            host="192.0.2.10",
            username="umbrel",
            identity_file=str(
                Path(self.temp.name) / "missing-identity"
            ),
            known_hosts_file=str(self.known_hosts),
        )

        runner = Mock()

        with self.assertRaisesRegex(
            ArtifactTransferError,
            "identity_file does not exist",
        ):
            SshArtifactTransport(
                runner=runner,
            ).transfer(
                target=target,
                request=self.request(),
                timeout_seconds=60,
            )

        runner.assert_not_called()


    def test_non_ssh_target_is_rejected(self):
        local = TransportTarget(
            asset_id="nexus-local",
            transport="local",
        )

        with self.assertRaisesRegex(
            ArtifactTransferError,
            "requires SSH",
        ):
            SshArtifactTransport().transfer(
                target=local,
                request=self.request(),
                timeout_seconds=60,
            )


if __name__ == "__main__":
    unittest.main()
