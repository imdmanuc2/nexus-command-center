from __future__ import annotations

import unittest

from backend.services.blockchain_target_platform import (
    TargetPlatformProfile,
    UMBREL_TARGET_PROFILE,
)
from backend.transports.models import (
    TransportResult,
    TransportTarget,
)
from backend.transports.target_prerequisites import (
    PYTHON_FEATURE_PROBE,
    SshTargetPrerequisiteTransport,
    TargetPrerequisiteError,
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
    host_key_verified=True,
    timed_out=False,
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


def success_results():
    return [
        result(),
        result(),
        result(),
        result(),
        result(),
        result(),
        result(),
        result(),
        result(stdout="Python 3.11.9\n"),
        result(stdout="filter=True;data=True\n"),
        result(
            stdout=(
                "tar (GNU tar) 1.34\n"
                "Copyright test\n"
            )
        ),
    ]


class TargetPrerequisiteTests(unittest.TestCase):
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

    def test_exact_fixed_prerequisite_sequence(self):
        fake = FakeTransport(
            success_results()
        )

        verifier = (
            SshTargetPrerequisiteTransport(
                transport=fake
            )
        )

        output = verifier.verify(
            target=self.target,
            profile=UMBREL_TARGET_PROFILE,
            timeout_seconds=30,
        )

        commands = [
            call[1]
            for call in fake.calls
        ]

        self.assertEqual(
            commands,
            [
                [
                    "/usr/bin/test",
                    "-d",
                    "/home/umbrel/umbrel",
                ],
                [
                    "/usr/bin/test",
                    "-w",
                    "/home/umbrel/umbrel",
                ],
                [
                    "/usr/bin/test",
                    "-d",
                    "/home/umbrel",
                ],
                [
                    "/usr/bin/test",
                    "-w",
                    "/home/umbrel",
                ],
                [
                    "/usr/bin/test",
                    "-x",
                    "/usr/bin/python3",
                ],
                [
                    "/usr/bin/test",
                    "-x",
                    "/usr/bin/tar",
                ],
                [
                    "/usr/bin/test",
                    "-x",
                    "/usr/bin/sha256sum",
                ],
                [
                    "/usr/bin/test",
                    "-x",
                    "/usr/bin/rm",
                ],
                [
                    "/usr/bin/python3",
                    "--version",
                ],
                [
                    "/usr/bin/python3",
                    "-c",
                    PYTHON_FEATURE_PROBE,
                ],
                [
                    "/usr/bin/tar",
                    "--version",
                ],
            ],
        )

        self.assertEqual(
            output.platform_id,
            "umbrel",
        )
        self.assertEqual(
            output.python_version,
            "Python 3.11.9",
        )
        self.assertEqual(
            output.tar_version,
            "tar (GNU tar) 1.34",
        )
        self.assertTrue(
            output.host_key_verified
        )

    def test_unknown_profile_fails_closed(self):
        profile = TargetPlatformProfile(
            platform_id="standalone-linux",
            staging_root="/tmp/stage",
            runtime_root="/opt/runtime",
            lifecycle_adapter_id="standalone-linux",
            test_path="/usr/bin/test",
            python3_path="/usr/bin/python3",
            tar_path="/usr/bin/tar",
            sha256sum_path="/usr/bin/sha256sum",
            rm_path="/usr/bin/rm",
        )

        fake = FakeTransport([])

        with self.assertRaisesRegex(
            TargetPrerequisiteError,
            "Unsupported target platform profile",
        ):
            SshTargetPrerequisiteTransport(
                transport=fake
            ).verify(
                target=self.target,
                profile=profile,
            )

        self.assertEqual(
            fake.calls,
            [],
        )

    def test_non_ssh_target_fails_before_execution(self):
        target = TransportTarget(
            asset_id="asset-1",
            transport="local",
        )

        fake = FakeTransport([])

        with self.assertRaisesRegex(
            TargetPrerequisiteError,
            "requires SSH",
        ):
            SshTargetPrerequisiteTransport(
                transport=fake
            ).verify(
                target=target,
                profile=UMBREL_TARGET_PROFILE,
            )

        self.assertEqual(
            fake.calls,
            [],
        )

    def test_timeout_must_be_positive(self):
        fake = FakeTransport([])

        with self.assertRaisesRegex(
            ValueError,
            "timeout must be positive",
        ):
            SshTargetPrerequisiteTransport(
                transport=fake
            ).verify(
                target=self.target,
                profile=UMBREL_TARGET_PROFILE,
                timeout_seconds=0,
            )

        self.assertEqual(
            fake.calls,
            [],
        )

    def test_failed_filesystem_check_stops_immediately(self):
        fake = FakeTransport([
            result(exit_code=1),
        ])

        with self.assertRaisesRegex(
            TargetPrerequisiteError,
            "runtime-parent-exists",
        ):
            SshTargetPrerequisiteTransport(
                transport=fake
            ).verify(
                target=self.target,
                profile=UMBREL_TARGET_PROFILE,
            )

        self.assertEqual(
            len(fake.calls),
            1,
        )

    def test_unverified_host_key_fails_closed(self):
        fake = FakeTransport([
            result(
                host_key_verified=False
            ),
        ])

        with self.assertRaisesRegex(
            TargetPrerequisiteError,
            "host key was not verified",
        ):
            SshTargetPrerequisiteTransport(
                transport=fake
            ).verify(
                target=self.target,
                profile=UMBREL_TARGET_PROFILE,
            )

        self.assertEqual(
            len(fake.calls),
            1,
        )

    def test_python_filter_support_is_required(self):
        results = success_results()
        results[9] = result(
            stdout="filter=False;data=False\n"
        )

        fake = FakeTransport(results)

        with self.assertRaisesRegex(
            TargetPrerequisiteError,
            "required tar extraction filter support",
        ):
            SshTargetPrerequisiteTransport(
                transport=fake
            ).verify(
                target=self.target,
                profile=UMBREL_TARGET_PROFILE,
            )

    def test_invalid_python_version_fails_closed(self):
        results = success_results()
        results[8] = result(
            stdout="unexpected\n"
        )

        fake = FakeTransport(results)

        with self.assertRaisesRegex(
            TargetPrerequisiteError,
            "invalid Python version response",
        ):
            SshTargetPrerequisiteTransport(
                transport=fake
            ).verify(
                target=self.target,
                profile=UMBREL_TARGET_PROFILE,
            )

    def test_timeout_result_fails_closed(self):
        fake = FakeTransport([
            result(
                timed_out=True
            ),
        ])

        with self.assertRaisesRegex(
            TargetPrerequisiteError,
            "operation timed out",
        ):
            SshTargetPrerequisiteTransport(
                transport=fake
            ).verify(
                target=self.target,
                profile=UMBREL_TARGET_PROFILE,
            )

    def test_result_contains_no_target_details(self):
        fake = FakeTransport(
            success_results()
        )

        output = (
            SshTargetPrerequisiteTransport(
                transport=fake
            ).verify(
                target=self.target,
                profile=UMBREL_TARGET_PROFILE,
            )
        )

        text = repr(output)

        self.assertNotIn(
            "192.0.2.10",
            text,
        )
        self.assertNotIn(
            "/private/",
            text,
        )
        self.assertNotIn(
            "username",
            text,
        )


if __name__ == "__main__":
    unittest.main()
