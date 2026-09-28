from __future__ import annotations

import json
import unittest

from backend.executors.blockchain_deployment_executor import (
    DeploymentRequest,
)
from backend.services.blockchain_bootstrap_invocation_service import (
    BlockchainBootstrapInvocationService,
    BootstrapInvocationContext,
)
from backend.services.blockchain_bootstrap_transfer_service import (
    BootstrapTransferContext,
)
from backend.services.blockchain_deployment_release_service import (
    DeploymentReleaseContext,
)
from backend.services.blockchain_runtime_transfer_service import (
    RuntimeTransferContext,
)
from backend.transports.bootstrap_invocation import (
    BootstrapInvocationResult,
)
from backend.transports.models import TransportTarget


BOOTSTRAP_SHA = "a" * 64
RUNTIME_SHA = "b" * 64
PAYLOAD_SHA = "c" * 64


class FakeInvocationTransport:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def invoke(
        self,
        *,
        target,
        request,
        timeout_seconds,
    ):
        self.calls.append(
            (target, request, timeout_seconds)
        )
        return self.result


class BootstrapInvocationServiceTests(unittest.TestCase):
    def setUp(self):
        self.request = DeploymentRequest(
            provider_id="bitcoin-mainnet",
            storage_target_id="storage-main",
            target_asset_id="asset-1",
            correlation_id="corr-1",
            approved_by="approval-1",
        )

        self.target = TransportTarget(
            asset_id="asset-1",
            transport="ssh",
            host="192.0.2.10",
            port=22,
            username="umbrel",
            identity_file="/private/key",
            known_hosts_file="/private/known_hosts",
        )

        self.release = DeploymentReleaseContext(
            release_id="release-1",
            runtime_version="1.0.0",
            source_revision="revision-1",
            bootstrap_artifact_id=(
                "seymour-bootstrap-1.0.0.tar.gz"
            ),
            bootstrap_source=__import__("pathlib").Path(
                "/trusted/bootstrap.tar.gz"
            ),
            bootstrap_sha256=BOOTSTRAP_SHA,
            runtime_artifact_id=(
                "seymour-runtime-1.0.0.tar.gz"
            ),
            runtime_source=__import__("pathlib").Path(
                "/trusted/runtime.tar.gz"
            ),
            runtime_sha256=RUNTIME_SHA,
            payload_manifest_sha256=PAYLOAD_SHA,
        )

        self.bootstrap = BootstrapTransferContext(
            artifact_id=self.release.bootstrap_artifact_id,
            remote_path="/private/bootstrap.tar.gz",
            sha256=BOOTSTRAP_SHA,
        )

        self.runtime = RuntimeTransferContext(
            artifact_id=self.release.runtime_artifact_id,
            remote_path="/private/runtime.tar.gz",
            sha256=RUNTIME_SHA,
        )

        self.result = BootstrapInvocationResult(
            bootstrap_sha256=BOOTSTRAP_SHA,
            runtime_sha256=RUNTIME_SHA,
            payload_manifest_sha256=PAYLOAD_SHA,
            runtime_version="1.0.0",
            source_revision="revision-1",
            duration_ms=250,
            exit_code=0,
            host_key_verified=True,
            result={
                "success": True,
                "installer": {
                    "status": "installed",
                },
            },
        )

        self.transport = FakeInvocationTransport(
            self.result
        )

        self.service = (
            BlockchainBootstrapInvocationService(
                target=self.target,
                transport=self.transport,
                timeout_seconds=900,
            )
        )

        self.private = {
            "resolve-release": self.release,
            "transfer-bootstrap": self.bootstrap,
            "transfer-runtime": self.runtime,
        }

    def test_maps_private_context_to_typed_invocation(self):
        output = self.service.invoke(
            self.request,
            {},
            self.private,
        )

        self.assertEqual(len(self.transport.calls), 1)

        target, request, timeout = (
            self.transport.calls[0]
        )

        self.assertIs(target, self.target)
        self.assertEqual(timeout, 900)

        self.assertEqual(
            request.bootstrap_artifact_id,
            self.release.bootstrap_artifact_id,
        )
        self.assertEqual(
            request.bootstrap_sha256,
            BOOTSTRAP_SHA,
        )
        self.assertEqual(
            request.runtime_artifact_id,
            self.release.runtime_artifact_id,
        )
        self.assertEqual(
            request.runtime_sha256,
            RUNTIME_SHA,
        )
        self.assertEqual(
            request.payload_manifest_sha256,
            PAYLOAD_SHA,
        )
        self.assertEqual(
            request.runtime_version,
            "1.0.0",
        )
        self.assertEqual(
            request.source_revision,
            "revision-1",
        )

        self.assertIsInstance(
            output.private,
            BootstrapInvocationContext,
        )

    def test_durable_evidence_is_sanitized(self):
        output = self.service.invoke(
            self.request,
            {},
            self.private,
        )

        encoded = json.dumps(output.evidence)

        self.assertNotIn("192.0.2.10", encoded)
        self.assertNotIn("/private/", encoded)
        self.assertNotIn("/trusted/", encoded)
        self.assertNotIn("umbrel", encoded)

        self.assertEqual(
            output.evidence,
            {
                "runtimeVersion": "1.0.0",
                "sourceRevision": "revision-1",
                "runtimeSha256": RUNTIME_SHA,
                "payloadManifestSha256": PAYLOAD_SHA,
                "durationMs": 250,
                "exitCode": 0,
                "hostKeyVerified": True,
            },
        )

    def test_remote_paths_are_not_used_as_request_inputs(self):
        self.service.invoke(
            self.request,
            {},
            self.private,
        )

        invocation_request = (
            self.transport.calls[0][1]
        )

        values = [
            str(value)
            for value in vars_for_dataclass(
                invocation_request
            ).values()
        ]

        self.assertNotIn(
            self.bootstrap.remote_path,
            values,
        )
        self.assertNotIn(
            self.runtime.remote_path,
            values,
        )

    def test_target_asset_mismatch_fails_before_transport(self):
        request = DeploymentRequest(
            provider_id="bitcoin-mainnet",
            storage_target_id="storage-main",
            target_asset_id="asset-other",
            correlation_id="corr-1",
            approved_by="approval-1",
        )

        with self.assertRaisesRegex(
            ValueError,
            "target asset mismatch",
        ):
            self.service.invoke(
                request,
                {},
                self.private,
            )

        self.assertEqual(self.transport.calls, [])

    def test_missing_release_context_fails_closed(self):
        private = dict(self.private)
        del private["resolve-release"]

        with self.assertRaisesRegex(
            ValueError,
            "resolve-release",
        ):
            self.service.invoke(
                self.request,
                {},
                private,
            )

        self.assertEqual(self.transport.calls, [])

    def test_missing_bootstrap_context_fails_closed(self):
        private = dict(self.private)
        del private["transfer-bootstrap"]

        with self.assertRaisesRegex(
            ValueError,
            "transfer-bootstrap",
        ):
            self.service.invoke(
                self.request,
                {},
                private,
            )

        self.assertEqual(self.transport.calls, [])

    def test_missing_runtime_context_fails_closed(self):
        private = dict(self.private)
        del private["transfer-runtime"]

        with self.assertRaisesRegex(
            ValueError,
            "transfer-runtime",
        ):
            self.service.invoke(
                self.request,
                {},
                private,
            )

        self.assertEqual(self.transport.calls, [])

    def test_bootstrap_transfer_identity_mismatch_fails_closed(self):
        private = dict(self.private)
        private["transfer-bootstrap"] = (
            BootstrapTransferContext(
                artifact_id="other.tar.gz",
                remote_path="/private/other.tar.gz",
                sha256=BOOTSTRAP_SHA,
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "Bootstrap transfer identity",
        ):
            self.service.invoke(
                self.request,
                {},
                private,
            )

        self.assertEqual(self.transport.calls, [])

    def test_runtime_transfer_sha_mismatch_fails_closed(self):
        private = dict(self.private)
        private["transfer-runtime"] = (
            RuntimeTransferContext(
                artifact_id=self.release.runtime_artifact_id,
                remote_path="/private/runtime.tar.gz",
                sha256="d" * 64,
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "Runtime transfer SHA",
        ):
            self.service.invoke(
                self.request,
                {},
                private,
            )

        self.assertEqual(self.transport.calls, [])

    def test_invocation_result_sha_mismatch_fails_closed(self):
        self.transport.result = (
            BootstrapInvocationResult(
                bootstrap_sha256="d" * 64,
                runtime_sha256=RUNTIME_SHA,
                payload_manifest_sha256=PAYLOAD_SHA,
                runtime_version="1.0.0",
                source_revision="revision-1",
                duration_ms=250,
                exit_code=0,
                host_key_verified=True,
                result={"success": True},
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "Bootstrap invocation SHA evidence",
        ):
            self.service.invoke(
                self.request,
                {},
                self.private,
            )

    def test_unverified_host_key_fails_closed(self):
        self.transport.result = (
            BootstrapInvocationResult(
                bootstrap_sha256=BOOTSTRAP_SHA,
                runtime_sha256=RUNTIME_SHA,
                payload_manifest_sha256=PAYLOAD_SHA,
                runtime_version="1.0.0",
                source_revision="revision-1",
                duration_ms=250,
                exit_code=0,
                host_key_verified=False,
                result={"success": True},
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "host key was not verified",
        ):
            self.service.invoke(
                self.request,
                {},
                self.private,
            )

    def test_timeout_must_be_positive(self):
        with self.assertRaisesRegex(
            ValueError,
            "timeout must be positive",
        ):
            BlockchainBootstrapInvocationService(
                target=self.target,
                transport=self.transport,
                timeout_seconds=0,
            )


def vars_for_dataclass(value):
    return {
        name: getattr(value, name)
        for name in value.__dataclass_fields__
    }


if __name__ == "__main__":
    unittest.main()
