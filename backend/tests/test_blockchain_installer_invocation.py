from __future__ import annotations

import json
import unittest

from backend.services.blockchain_target_platform import (
    TargetPlatformProfile,
    UMBREL_TARGET_PROFILE,
)
from backend.transports.blockchain_installer_invocation import (
    BlockchainInstallerInvocationError,
    BlockchainInstallerInvocationRequest,
    SshBlockchainInstallerInvocationTransport,
)
from backend.transports.models import (
    TransportResult,
    TransportTarget,
)


class FakeTransport:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def execute(
        self,
        *,
        target,
        argv,
        timeout_seconds,
    ):
        self.calls.append(
            {
                "target": target,
                "argv": list(argv),
                "timeout": timeout_seconds,
            }
        )

        if not self.results:
            raise AssertionError(
                "Unexpected transport call"
            )

        return self.results.pop(0)


def result(
    *,
    payload=None,
    stdout=None,
    stderr="",
    exit_code=0,
    timed_out=False,
    host_key_verified=True,
):
    if stdout is None:
        stdout = json.dumps(
            payload
            if payload is not None
            else {
                "operationId": "op-test-install",
                "status": "succeeded",
                "result": {},
                "verification": {
                    "verified": True,
                    "evidence": {},
                    "error": None,
                },
                "error": None,
            }
        ) + "\n"

    return TransportResult(
        transport="ssh",
        target_asset_id="asset-1",
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_ms=1,
        timed_out=timed_out,
        host_key_verified=host_key_verified,
        metadata={},
    )


class BlockchainInstallerInvocationTests(
    unittest.TestCase
):
    def setUp(self):
        self.target = TransportTarget(
            asset_id="asset-1",
            transport="ssh",
            host="192.0.2.10",
            port=22,
            username="umbrel",
            identity_file="/private/key",
            known_hosts_file="/private/known_hosts",
        )

        self.request = (
            BlockchainInstallerInvocationRequest(
                provider_id="bitcoin-mainnet",
                storage_target_id="storage-main",
            )
        )

    def verifier(
        self,
        results,
        profile=UMBREL_TARGET_PROFILE,
    ):
        fake = FakeTransport(results)

        transport = (
            SshBlockchainInstallerInvocationTransport(
                profile=profile,
                transport=fake,
            )
        )

        return transport, fake

    def test_exact_fixed_installer_command(self):
        transport, fake = self.verifier([
            result(),
        ])

        output = transport.invoke(
            target=self.target,
            request=self.request,
            timeout_seconds=900,
        )

        self.assertEqual(
            fake.calls[0]["argv"],
            [
                (
                    "/home/umbrel/umbrel/"
                    "seymour-runtime/scripts/"
                    "seymour-blockchain-install"
                ),
                "--execute",
                "--provider-id",
                "bitcoin-mainnet",
                "--storage-target-id",
                "storage-main",
            ],
        )

        self.assertEqual(
            fake.calls[0]["timeout"],
            900,
        )

        self.assertTrue(output.success)
        self.assertEqual(
            output.provider_id,
            "bitcoin-mainnet",
        )
        self.assertEqual(
            output.storage_target_id,
            "storage-main",
        )

    def test_provider_id_is_validated_before_transport(self):
        transport, fake = self.verifier([])

        bad = (
            BlockchainInstallerInvocationRequest(
                provider_id="../../bad",
                storage_target_id="storage-main",
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "Invalid provider_id",
        ):
            transport.invoke(
                target=self.target,
                request=bad,
            )

        self.assertEqual(fake.calls, [])

    def test_storage_target_is_validated_before_transport(self):
        transport, fake = self.verifier([])

        bad = (
            BlockchainInstallerInvocationRequest(
                provider_id="bitcoin-mainnet",
                storage_target_id="../../bad",
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "Invalid storage_target_id",
        ):
            transport.invoke(
                target=self.target,
                request=bad,
            )

        self.assertEqual(fake.calls, [])

    def test_non_ssh_target_fails_before_transport(self):
        target = TransportTarget(
            asset_id="asset-1",
            transport="local",
        )

        transport, fake = self.verifier([])

        with self.assertRaisesRegex(
            BlockchainInstallerInvocationError,
            "requires SSH",
        ):
            transport.invoke(
                target=target,
                request=self.request,
            )

        self.assertEqual(fake.calls, [])

    def test_unknown_platform_fails_before_transport(self):
        profile = TargetPlatformProfile(
            platform_id="standalone-linux",
            staging_root="/tmp/stage",
            runtime_root="/opt/seymour/runtime",
            lifecycle_adapter_id="standalone-linux",
            test_path="/usr/bin/test",
            python3_path="/usr/bin/python3",
            tar_path="/usr/bin/tar",
            sha256sum_path="/usr/bin/sha256sum",
            rm_path="/usr/bin/rm",
        )

        transport, fake = self.verifier(
            [],
            profile=profile,
        )

        with self.assertRaisesRegex(
            BlockchainInstallerInvocationError,
            "Unsupported target platform profile",
        ):
            transport.invoke(
                target=self.target,
                request=self.request,
            )

        self.assertEqual(fake.calls, [])

    def test_timeout_must_be_positive(self):
        transport, fake = self.verifier([])

        with self.assertRaisesRegex(
            ValueError,
            "timeout must be positive",
        ):
            transport.invoke(
                target=self.target,
                request=self.request,
                timeout_seconds=0,
            )

        self.assertEqual(fake.calls, [])

    def test_transport_timeout_fails_closed(self):
        transport, _ = self.verifier([
            result(timed_out=True),
        ])

        with self.assertRaisesRegex(
            BlockchainInstallerInvocationError,
            "timed out",
        ):
            transport.invoke(
                target=self.target,
                request=self.request,
            )

    def test_nonzero_exit_fails_closed(self):
        transport, _ = self.verifier([
            result(exit_code=1),
        ])

        with self.assertRaisesRegex(
            BlockchainInstallerInvocationError,
            "invocation failed",
        ):
            transport.invoke(
                target=self.target,
                request=self.request,
            )

    def test_unverified_host_key_fails_closed(self):
        transport, _ = self.verifier([
            result(host_key_verified=False),
        ])

        with self.assertRaisesRegex(
            BlockchainInstallerInvocationError,
            "host key was not verified",
        ):
            transport.invoke(
                target=self.target,
                request=self.request,
            )

    def test_invalid_json_fails_closed(self):
        transport, _ = self.verifier([
            result(stdout="not-json\n"),
        ])

        with self.assertRaisesRegex(
            BlockchainInstallerInvocationError,
            "invalid JSON",
        ):
            transport.invoke(
                target=self.target,
                request=self.request,
            )

    def test_failed_status_fails_closed(self):
        transport, _ = self.verifier([
            result(
                payload={
                    "operationId": "op-test-install",
                    "status": "failed",
                    "result": {},
                    "verification": {
                        "verified": False,
                        "evidence": {},
                        "error": "install failed",
                    },
                    "error": "install failed",
                }
            ),
        ])

        with self.assertRaisesRegex(
            BlockchainInstallerInvocationError,
            "succeeded status",
        ):
            transport.invoke(
                target=self.target,
                request=self.request,
            )

    def test_missing_operation_id_fails_closed(self):
        transport, _ = self.verifier([
            result(
                payload={
                    "operationId": "",
                    "status": "succeeded",
                    "result": {},
                    "verification": {
                        "verified": True,
                        "evidence": {},
                        "error": None,
                    },
                    "error": None,
                }
            ),
        ])

        with self.assertRaisesRegex(
            BlockchainInstallerInvocationError,
            "missing operationId",
        ):
            transport.invoke(
                target=self.target,
                request=self.request,
            )

    def test_unverified_result_fails_closed(self):
        transport, _ = self.verifier([
            result(
                payload={
                    "operationId": "op-test-install",
                    "status": "succeeded",
                    "result": {},
                    "verification": {
                        "verified": False,
                        "evidence": {},
                        "error": "verification failed",
                    },
                    "error": None,
                }
            ),
        ])

        with self.assertRaisesRegex(
            BlockchainInstallerInvocationError,
            "verification did not succeed",
        ):
            transport.invoke(
                target=self.target,
                request=self.request,
            )

    def test_result_contains_no_target_or_path_details(self):
        transport, _ = self.verifier([
            result(),
        ])

        output = transport.invoke(
            target=self.target,
            request=self.request,
        )

        text = repr(output)

        self.assertNotIn(
            "192.0.2.10",
            text,
        )
        self.assertNotIn(
            "/home/umbrel",
            text,
        )
        self.assertNotIn(
            "/private/",
            text,
        )

    def test_request_has_no_command_or_path_surface(self):
        fields = set(
            self.request.__dataclass_fields__
        )

        forbidden = {
            "command",
            "argv",
            "shell",
            "executable",
            "runtime_root",
            "remote_path",
            "host",
            "username",
            "password",
            "identity_file",
            "known_hosts_file",
        }

        self.assertTrue(
            forbidden.isdisjoint(fields)
        )


if __name__ == "__main__":
    unittest.main()
