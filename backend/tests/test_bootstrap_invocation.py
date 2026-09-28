from __future__ import annotations

import unittest

from backend.transports.bootstrap_invocation import (
    BOOTSTRAP_DIR,
    BOOTSTRAP_PROGRAM,
    REMOTE_STAGE_ROOT,
    BootstrapInvocationError,
    BootstrapInvocationRequest,
    SshBootstrapInvocationTransport,
)
from backend.transports.models import (
    TransportResult,
    TransportTarget,
)


BOOTSTRAP_SHA = "a" * 64
RUNTIME_SHA = "b" * 64
PAYLOAD_SHA = "c" * 64


class FakeTransport:
    def __init__(self):
        self.calls = []
        self.results = []

    def execute(
        self,
        *,
        target,
        argv,
        timeout_seconds,
    ):
        self.calls.append(
            (target, list(argv), timeout_seconds)
        )

        if not self.results:
            raise AssertionError(
                "unexpected transport call"
            )

        return self.results.pop(0)


def result(
    *,
    stdout="",
    exit_code=0,
    host_key_verified=True,
):
    return TransportResult(
        target_asset_id="asset-1",
        exit_code=exit_code,
        stdout=stdout,
        stderr="",
        duration_ms=1,
        timed_out=False,
        transport="ssh",
        host_key_verified=host_key_verified,
    )


class BootstrapInvocationTests(unittest.TestCase):
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

        self.request = BootstrapInvocationRequest(
            bootstrap_artifact_id=(
                "seymour-bootstrap-1.0.0.tar.gz"
            ),
            bootstrap_sha256=BOOTSTRAP_SHA,
            runtime_artifact_id=(
                "seymour-runtime-1.0.0.tar.gz"
            ),
            runtime_sha256=RUNTIME_SHA,
            payload_manifest_sha256=PAYLOAD_SHA,
            runtime_version="1.0.0",
            source_revision="revision-1",
        )

        self.fake = FakeTransport()

        ticks = iter([10.0, 10.5])

        self.transport = (
            SshBootstrapInvocationTransport(
                transport=self.fake,
                clock=lambda: next(ticks),
            )
        )

    def success_results(self):
        self.fake.results = [
            result(
                stdout=(
                    BOOTSTRAP_SHA
                    + "  "
                    + REMOTE_STAGE_ROOT
                    + "/seymour-bootstrap-1.0.0.tar.gz\n"
                )
            ),
            result(
                stdout=(
                    RUNTIME_SHA
                    + "  "
                    + REMOTE_STAGE_ROOT
                    + "/seymour-runtime-1.0.0.tar.gz\n"
                )
            ),
            result(
                stdout=(
                    "seymour-bootstrap/bootstrap.py\n"
                    "seymour-bootstrap/runtime_installer.py\n"
                )
            ),
            result(),
            result(),
            result(
                stdout=(
                    '{"success":true,'
                    '"archiveSha256":"'
                    + RUNTIME_SHA
                    + '",'
                    '"payloadManifestSha256":"'
                    + PAYLOAD_SHA
                    + '",'
                    '"runtimeVersion":"1.0.0",'
                    '"sourceRevision":"revision-1",'
                    '"installer":{"status":"installed"}}'
                )
            ),
        ]

    def test_exact_fixed_command_sequence(self):
        self.success_results()

        output = self.transport.invoke(
            target=self.target,
            request=self.request,
            timeout_seconds=120,
        )

        commands = [
            call[1]
            for call in self.fake.calls
        ]

        bootstrap_archive = (
            REMOTE_STAGE_ROOT
            + "/seymour-bootstrap-1.0.0.tar.gz"
        )
        runtime_archive = (
            REMOTE_STAGE_ROOT
            + "/seymour-runtime-1.0.0.tar.gz"
        )

        self.assertEqual(
            commands,
            [
                [
                    "/usr/bin/sha256sum",
                    "--",
                    bootstrap_archive,
                ],
                [
                    "/usr/bin/sha256sum",
                    "--",
                    runtime_archive,
                ],
                [
                    "/usr/bin/tar",
                    "-tzf",
                    bootstrap_archive,
                ],
                [
                    "/usr/bin/rm",
                    "-rf",
                    "--",
                    BOOTSTRAP_DIR,
                ],
                [
                    "/usr/bin/tar",
                    "-xzf",
                    bootstrap_archive,
                    "-C",
                    REMOTE_STAGE_ROOT,
                ],
                [
                    "/usr/bin/python3",
                    BOOTSTRAP_PROGRAM,
                    "--archive",
                    runtime_archive,
                    "--archive-sha256",
                    RUNTIME_SHA,
                    "--payload-manifest-sha256",
                    PAYLOAD_SHA,
                    "--runtime-version",
                    "1.0.0",
                    "--source-revision",
                    "revision-1",
                ],
            ],
        )

        self.assertEqual(
            output.runtime_sha256,
            RUNTIME_SHA,
        )
        self.assertEqual(output.duration_ms, 500)

    def test_non_ssh_target_rejected_before_execution(self):
        target = TransportTarget(
            asset_id="asset-1",
            transport="local",
        )

        with self.assertRaisesRegex(
            BootstrapInvocationError,
            "requires SSH",
        ):
            self.transport.invoke(
                target=target,
                request=self.request,
                timeout_seconds=120,
            )

        self.assertEqual(self.fake.calls, [])

    def test_bootstrap_hash_mismatch_stops_before_runtime(self):
        self.fake.results = [
            result(stdout=("d" * 64) + "  file\n")
        ]

        with self.assertRaisesRegex(
            BootstrapInvocationError,
            "bootstrap SHA-256 mismatch",
        ):
            self.transport.invoke(
                target=self.target,
                request=self.request,
                timeout_seconds=120,
            )

        self.assertEqual(len(self.fake.calls), 1)

    def test_runtime_hash_mismatch_stops_before_listing(self):
        self.fake.results = [
            result(stdout=BOOTSTRAP_SHA + "  file\n"),
            result(stdout=("d" * 64) + "  file\n"),
        ]

        with self.assertRaisesRegex(
            BootstrapInvocationError,
            "runtime SHA-256 mismatch",
        ):
            self.transport.invoke(
                target=self.target,
                request=self.request,
                timeout_seconds=120,
            )

        self.assertEqual(len(self.fake.calls), 2)

    def test_member_contract_mismatch_stops_before_extraction(self):
        self.fake.results = [
            result(stdout=BOOTSTRAP_SHA + "  file\n"),
            result(stdout=RUNTIME_SHA + "  file\n"),
            result(
                stdout=(
                    "seymour-bootstrap/bootstrap.py\n"
                    "seymour-bootstrap/evil.py\n"
                )
            ),
        ]

        with self.assertRaisesRegex(
            BootstrapInvocationError,
            "member contract mismatch",
        ):
            self.transport.invoke(
                target=self.target,
                request=self.request,
                timeout_seconds=120,
            )

        self.assertEqual(len(self.fake.calls), 3)

    def test_failed_remote_operation_fails_closed(self):
        self.fake.results = [
            result(
                stdout=BOOTSTRAP_SHA + "  file\n",
                exit_code=1,
            )
        ]

        with self.assertRaisesRegex(
            BootstrapInvocationError,
            "remote operation failed",
        ):
            self.transport.invoke(
                target=self.target,
                request=self.request,
                timeout_seconds=120,
            )

    def test_unverified_host_key_fails_closed(self):
        self.fake.results = [
            result(
                stdout=BOOTSTRAP_SHA + "  file\n",
                host_key_verified=False,
            )
        ]

        with self.assertRaisesRegex(
            BootstrapInvocationError,
            "host key was not verified",
        ):
            self.transport.invoke(
                target=self.target,
                request=self.request,
                timeout_seconds=120,
            )

    def test_invalid_json_fails_closed(self):
        self.success_results()
        self.fake.results[-1] = result(
            stdout="not-json"
        )

        with self.assertRaisesRegex(
            BootstrapInvocationError,
            "invalid JSON",
        ):
            self.transport.invoke(
                target=self.target,
                request=self.request,
                timeout_seconds=120,
            )

    def test_bootstrap_reported_failure_fails_closed(self):
        self.success_results()
        self.fake.results[-1] = result(
            stdout='{"success":false}'
        )

        with self.assertRaisesRegex(
            BootstrapInvocationError,
            "reported failure",
        ):
            self.transport.invoke(
                target=self.target,
                request=self.request,
                timeout_seconds=120,
            )

    def test_result_evidence_mismatch_fails_closed(self):
        self.success_results()
        self.fake.results[-1] = result(
            stdout=(
                '{"success":true,'
                '"archiveSha256":"'
                + ("d" * 64)
                + '",'
                '"payloadManifestSha256":"'
                + PAYLOAD_SHA
                + '",'
                '"runtimeVersion":"1.0.0",'
                '"sourceRevision":"revision-1"}'
            )
        )

        with self.assertRaisesRegex(
            BootstrapInvocationError,
            "runtime SHA evidence mismatch",
        ):
            self.transport.invoke(
                target=self.target,
                request=self.request,
                timeout_seconds=120,
            )

    def test_artifact_ids_cannot_supply_paths(self):
        bad = BootstrapInvocationRequest(
            bootstrap_artifact_id="../bootstrap.tar.gz",
            bootstrap_sha256=BOOTSTRAP_SHA,
            runtime_artifact_id="runtime.tar.gz",
            runtime_sha256=RUNTIME_SHA,
            payload_manifest_sha256=PAYLOAD_SHA,
            runtime_version="1.0.0",
            source_revision="revision-1",
        )

        with self.assertRaisesRegex(
            BootstrapInvocationError,
            "artifact ID is invalid",
        ):
            self.transport.invoke(
                target=self.target,
                request=bad,
                timeout_seconds=120,
            )

        self.assertEqual(self.fake.calls, [])

    def test_timeout_must_be_positive(self):
        with self.assertRaisesRegex(
            BootstrapInvocationError,
            "timeout must be positive",
        ):
            self.transport.invoke(
                target=self.target,
                request=self.request,
                timeout_seconds=0,
            )

        self.assertEqual(self.fake.calls, [])


if __name__ == "__main__":
    unittest.main()
