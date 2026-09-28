from __future__ import annotations

import json
import unittest

from backend.services.blockchain_target_platform import (
    TargetPlatformProfile,
    UMBREL_TARGET_PROFILE,
)
from backend.transports.models import (
    TransportResult,
    TransportTarget,
)
from backend.transports.runtime_verification import (
    RuntimeVerificationError,
    RuntimeVerificationRequest,
    SshRuntimeVerificationTransport,
)


PAYLOAD_SHA = "a" * 64


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
            (
                target,
                list(argv),
                timeout_seconds,
            )
        )

        if not self.results:
            raise AssertionError(
                "Unexpected transport call"
            )

        return self.results.pop(0)


def result(
    *,
    stdout="",
    stderr="",
    exit_code=0,
    timed_out=False,
    host_key_verified=True,
):
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


def evidence(
    *,
    runtime_version="1.0.0",
    source_revision="revision-1",
    payload_sha=PAYLOAD_SHA,
):
    return json.dumps(
        {
            "runtimeVersion": runtime_version,
            "sourceRevision": source_revision,
            "payloadManifestSha256": payload_sha,
        }
    ) + "\n"


class RuntimeVerificationTests(unittest.TestCase):
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

        self.request = RuntimeVerificationRequest(
            runtime_version="1.0.0",
            source_revision="revision-1",
            payload_manifest_sha256=PAYLOAD_SHA,
        )

    def verifier(self, results, profile=UMBREL_TARGET_PROFILE):
        fake = FakeTransport(results)

        verifier = SshRuntimeVerificationTransport(
            profile=profile,
            transport=fake,
        )

        return verifier, fake

    def test_exact_fixed_verification_sequence(self):
        verifier, fake = self.verifier([
            result(),
            result(),
            result(stdout=evidence()),
        ])

        output = verifier.verify(
            target=self.target,
            request=self.request,
            timeout_seconds=30,
        )

        commands = [
            call[1]
            for call in fake.calls
        ]

        self.assertEqual(
            commands[0],
            [
                "/usr/bin/test",
                "-d",
                "/home/umbrel/umbrel/seymour-runtime",
            ],
        )

        self.assertEqual(
            commands[1],
            [
                "/usr/bin/test",
                "-x",
                (
                    "/home/umbrel/umbrel/seymour-runtime/"
                    "scripts/seymour-blockchain-install"
                ),
            ],
        )

        self.assertEqual(
            commands[2][0],
            "/usr/bin/python3",
        )
        self.assertEqual(
            commands[2][-1],
            (
                "/home/umbrel/umbrel/seymour-runtime/"
                "runtime-installation.json"
            ),
        )

        self.assertEqual(
            output.runtime_version,
            "1.0.0",
        )
        self.assertEqual(
            output.source_revision,
            "revision-1",
        )
        self.assertEqual(
            output.payload_manifest_sha256,
            PAYLOAD_SHA,
        )
        self.assertTrue(
            output.executable_present
        )

    def test_runtime_root_failure_stops_immediately(self):
        verifier, fake = self.verifier([
            result(exit_code=1),
        ])

        with self.assertRaisesRegex(
            RuntimeVerificationError,
            "runtime-root",
        ):
            verifier.verify(
                target=self.target,
                request=self.request,
            )

        self.assertEqual(
            len(fake.calls),
            1,
        )

    def test_executable_failure_stops_before_evidence(self):
        verifier, fake = self.verifier([
            result(),
            result(exit_code=1),
        ])

        with self.assertRaisesRegex(
            RuntimeVerificationError,
            "runtime-executable",
        ):
            verifier.verify(
                target=self.target,
                request=self.request,
            )

        self.assertEqual(
            len(fake.calls),
            2,
        )

    def test_runtime_version_mismatch_fails_closed(self):
        verifier, _ = self.verifier([
            result(),
            result(),
            result(
                stdout=evidence(
                    runtime_version="2.0.0"
                )
            ),
        ])

        with self.assertRaisesRegex(
            RuntimeVerificationError,
            "runtime version mismatch",
        ):
            verifier.verify(
                target=self.target,
                request=self.request,
            )

    def test_source_revision_mismatch_fails_closed(self):
        verifier, _ = self.verifier([
            result(),
            result(),
            result(
                stdout=evidence(
                    source_revision="wrong"
                )
            ),
        ])

        with self.assertRaisesRegex(
            RuntimeVerificationError,
            "source revision mismatch",
        ):
            verifier.verify(
                target=self.target,
                request=self.request,
            )

    def test_payload_manifest_mismatch_fails_closed(self):
        verifier, _ = self.verifier([
            result(),
            result(),
            result(
                stdout=evidence(
                    payload_sha="b" * 64
                )
            ),
        ])

        with self.assertRaisesRegex(
            RuntimeVerificationError,
            "payload manifest mismatch",
        ):
            verifier.verify(
                target=self.target,
                request=self.request,
            )

    def test_invalid_json_fails_closed(self):
        verifier, _ = self.verifier([
            result(),
            result(),
            result(stdout="not-json\n"),
        ])

        with self.assertRaisesRegex(
            RuntimeVerificationError,
            "invalid JSON",
        ):
            verifier.verify(
                target=self.target,
                request=self.request,
            )

    def test_unverified_host_key_fails_closed(self):
        verifier, fake = self.verifier([
            result(host_key_verified=False),
        ])

        with self.assertRaisesRegex(
            RuntimeVerificationError,
            "host key was not verified",
        ):
            verifier.verify(
                target=self.target,
                request=self.request,
            )

        self.assertEqual(
            len(fake.calls),
            1,
        )

    def test_timeout_fails_closed(self):
        verifier, _ = self.verifier([
            result(timed_out=True),
        ])

        with self.assertRaisesRegex(
            RuntimeVerificationError,
            "operation timed out",
        ):
            verifier.verify(
                target=self.target,
                request=self.request,
            )

    def test_non_ssh_target_fails_before_execution(self):
        target = TransportTarget(
            asset_id="asset-1",
            transport="local",
        )

        verifier, fake = self.verifier([])

        with self.assertRaisesRegex(
            RuntimeVerificationError,
            "requires SSH",
        ):
            verifier.verify(
                target=target,
                request=self.request,
            )

        self.assertEqual(
            fake.calls,
            [],
        )

    def test_unknown_platform_fails_before_execution(self):
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

        verifier, fake = self.verifier(
            [],
            profile=profile,
        )

        with self.assertRaisesRegex(
            RuntimeVerificationError,
            "Unsupported target platform profile",
        ):
            verifier.verify(
                target=self.target,
                request=self.request,
            )

        self.assertEqual(
            fake.calls,
            [],
        )

    def test_timeout_must_be_positive(self):
        verifier, fake = self.verifier([])

        with self.assertRaisesRegex(
            ValueError,
            "timeout must be positive",
        ):
            verifier.verify(
                target=self.target,
                request=self.request,
                timeout_seconds=0,
            )

        self.assertEqual(
            fake.calls,
            [],
        )

    def test_bad_payload_sha_fails_before_execution(self):
        verifier, fake = self.verifier([])

        request = RuntimeVerificationRequest(
            runtime_version="1.0.0",
            source_revision="revision-1",
            payload_manifest_sha256="bad",
        )

        with self.assertRaisesRegex(
            ValueError,
            "Invalid payload_manifest_sha256",
        ):
            verifier.verify(
                target=self.target,
                request=request,
            )

        self.assertEqual(
            fake.calls,
            [],
        )

    def test_result_contains_no_target_or_path_details(self):
        verifier, _ = self.verifier([
            result(),
            result(),
            result(stdout=evidence()),
        ])

        output = verifier.verify(
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


if __name__ == "__main__":
    unittest.main()
