from __future__ import annotations

import json
import unittest

from backend.services.blockchain_target_platform import (
    TargetPlatformProfile,
    UMBREL_TARGET_PROFILE,
)
from backend.transports.installation_verification import (
    INSTALLATION_CONTRACT,
    INSTALLATION_CONTRACT_VERSION,
    InstallationVerificationError,
    InstallationVerificationRequest,
    SshInstallationVerificationTransport,
)
from backend.transports.models import (
    TransportResult,
    TransportTarget,
)


def evidence(**updates):
    value = {
        "contract": INSTALLATION_CONTRACT,
        "version": INSTALLATION_CONTRACT_VERSION,
        "operationId": "op-test-install",
        "operation": "install",
        "providerId": "bitcoin-mainnet",
        "storageTargetId": "storage-main",
        "status": "installed",
        "verified": True,
        "stateVerified": True,
        "runtimeDataMountMatches": True,
        "runtimeBlocksMountMatches": True,
        "bindingMode": "single-path",
        "recordedAt": "2026-09-10T00:00:00+00:00",
    }
    value.update(updates)
    return value


def result(
    *,
    payload=None,
    stdout=None,
    exit_code=0,
    timed_out=False,
    host_key_verified=True,
):
    if stdout is None:
        stdout = json.dumps(
            payload if payload is not None
            else evidence()
        )

    return TransportResult(
        transport="ssh",
        target_asset_id="asset-1",
        exit_code=exit_code,
        stdout=stdout,
        stderr="",
        duration_ms=1,
        timed_out=timed_out,
        host_key_verified=host_key_verified,
        metadata={},
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
        self.calls.append({
            "target": target,
            "argv": list(argv),
            "timeout": timeout_seconds,
        })

        if not self.results:
            raise AssertionError(
                "Unexpected transport call"
            )

        return self.results.pop(0)


class InstallationVerificationTests(
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

        self.request = InstallationVerificationRequest(
            provider_id="bitcoin-mainnet",
        )

    def verifier(
        self,
        results,
        profile=UMBREL_TARGET_PROFILE,
    ):
        fake = FakeTransport(results)

        transport = (
            SshInstallationVerificationTransport(
                profile=profile,
                transport=fake,
            )
        )

        return transport, fake

    def test_exact_fixed_evidence_query_command(self):
        transport, fake = self.verifier([
            result(),
        ])

        output = transport.verify(
            target=self.target,
            request=self.request,
        )

        self.assertEqual(
            fake.calls[0]["argv"],
            [
                (
                    UMBREL_TARGET_PROFILE.runtime_root
                    + "/scripts/"
                    + "seymour-blockchain-install-evidence"
                ),
                "--provider-id",
                "bitcoin-mainnet",
            ],
        )

        self.assertEqual(
            output.operation_id,
            "op-test-install",
        )
        self.assertTrue(output.verified)

    def test_request_has_no_path_or_command_surface(self):
        fields = set(
            self.request.__dataclass_fields__
        )

        self.assertEqual(
            fields,
            {"provider_id"},
        )

    def test_non_ssh_fails_before_transport(self):
        target = TransportTarget(
            asset_id="asset-1",
            transport="local",
        )

        transport, fake = self.verifier([])

        with self.assertRaisesRegex(
            InstallationVerificationError,
            "requires SSH",
        ):
            transport.verify(
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
            InstallationVerificationError,
            "Unsupported target platform",
        ):
            transport.verify(
                target=self.target,
                request=self.request,
            )

        self.assertEqual(fake.calls, [])

    def test_invalid_provider_fails_before_transport(self):
        transport, fake = self.verifier([])

        bad = InstallationVerificationRequest(
            provider_id="../escape",
        )

        with self.assertRaisesRegex(
            ValueError,
            "provider_id is invalid",
        ):
            transport.verify(
                target=self.target,
                request=bad,
            )

        self.assertEqual(fake.calls, [])

    def test_timeout_fails_closed(self):
        transport, _ = self.verifier([
            result(timed_out=True),
        ])

        with self.assertRaisesRegex(
            InstallationVerificationError,
            "timed out",
        ):
            transport.verify(
                target=self.target,
                request=self.request,
            )

    def test_host_key_failure_fails_closed(self):
        transport, _ = self.verifier([
            result(host_key_verified=False),
        ])

        with self.assertRaisesRegex(
            InstallationVerificationError,
            "host key was not verified",
        ):
            transport.verify(
                target=self.target,
                request=self.request,
            )

    def test_nonzero_query_fails_closed(self):
        transport, _ = self.verifier([
            result(exit_code=1),
        ])

        with self.assertRaisesRegex(
            InstallationVerificationError,
            "query failed",
        ):
            transport.verify(
                target=self.target,
                request=self.request,
            )

    def test_invalid_json_fails_closed(self):
        transport, _ = self.verifier([
            result(stdout="not-json"),
        ])

        with self.assertRaisesRegex(
            InstallationVerificationError,
            "invalid JSON",
        ):
            transport.verify(
                target=self.target,
                request=self.request,
            )

    def test_contract_mismatch_fails_closed(self):
        transport, _ = self.verifier([
            result(
                payload=evidence(
                    contract="wrong"
                )
            ),
        ])

        with self.assertRaisesRegex(
            InstallationVerificationError,
            "contract mismatch",
        ):
            transport.verify(
                target=self.target,
                request=self.request,
            )

    def test_version_mismatch_fails_closed(self):
        transport, _ = self.verifier([
            result(
                payload=evidence(
                    version=2
                )
            ),
        ])

        with self.assertRaisesRegex(
            InstallationVerificationError,
            "version mismatch",
        ):
            transport.verify(
                target=self.target,
                request=self.request,
            )

    def test_operation_mismatch_fails_closed(self):
        transport, _ = self.verifier([
            result(
                payload=evidence(
                    operation="update"
                )
            ),
        ])

        with self.assertRaisesRegex(
            InstallationVerificationError,
            "operation mismatch",
        ):
            transport.verify(
                target=self.target,
                request=self.request,
            )

    def test_status_mismatch_fails_closed(self):
        transport, _ = self.verifier([
            result(
                payload=evidence(
                    status="failed"
                )
            ),
        ])

        with self.assertRaisesRegex(
            InstallationVerificationError,
            "status is not installed",
        ):
            transport.verify(
                target=self.target,
                request=self.request,
            )

    def test_provider_mismatch_fails_closed(self):
        transport, _ = self.verifier([
            result(
                payload=evidence(
                    providerId="wrong-provider"
                )
            ),
        ])

        with self.assertRaisesRegex(
            InstallationVerificationError,
            "provider mismatch",
        ):
            transport.verify(
                target=self.target,
                request=self.request,
            )

    def test_each_verification_assertion_fails_closed(self):
        cases = (
            ("verified", "verified"),
            (
                "stateVerified",
                "state verification",
            ),
            (
                "runtimeDataMountMatches",
                "data mount verification",
            ),
            (
                "runtimeBlocksMountMatches",
                "blocks mount verification",
            ),
        )

        for field, message in cases:
            with self.subTest(field=field):
                transport, _ = self.verifier([
                    result(
                        payload=evidence(
                            **{field: False}
                        )
                    ),
                ])

                with self.assertRaisesRegex(
                    InstallationVerificationError,
                    message,
                ):
                    transport.verify(
                        target=self.target,
                        request=self.request,
                    )

    def test_required_identity_fields_fail_closed(self):
        for field in (
            "operationId",
            "storageTargetId",
            "bindingMode",
            "recordedAt",
        ):
            with self.subTest(field=field):
                transport, _ = self.verifier([
                    result(
                        payload=evidence(
                            **{field: ""}
                        )
                    ),
                ])

                with self.assertRaisesRegex(
                    InstallationVerificationError,
                    "missing",
                ):
                    transport.verify(
                        target=self.target,
                        request=self.request,
                    )

    def test_result_contains_no_target_or_path_details(self):
        transport, _ = self.verifier([
            result(),
        ])

        output = transport.verify(
            target=self.target,
            request=self.request,
        )

        encoded = repr(output)

        self.assertNotIn(
            "192.0.2.10",
            encoded,
        )
        self.assertNotIn(
            "/home/umbrel",
            encoded,
        )
        self.assertNotIn(
            "/private/",
            encoded,
        )


if __name__ == "__main__":
    unittest.main()
