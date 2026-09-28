from __future__ import annotations

import unittest

from backend.executors.blockchain_deployment_executor import (
    BlockchainDeploymentError,
    BlockchainDeploymentExecutor,
    DeploymentRequest,
    DeploymentStepOutput,
)


class BlockchainDeploymentExecutorTests(unittest.TestCase):
    def request(self) -> DeploymentRequest:
        return DeploymentRequest(
            provider_id="btc",
            storage_target_id="storage-main",
            target_asset_id="asset-test",
            correlation_id="corr-test",
            approved_by="approval-test",
        )

    def executor(self, calls, *, fail_step=None, bad_step=None):
        def handler(step_id):
            def run(request, context=None, private_context=None):
                calls.append(step_id)

                self.assertEqual(request.provider_id, "btc")
                self.assertEqual(
                    request.storage_target_id,
                    "storage-main",
                )

                if step_id == fail_step:
                    raise RuntimeError("injected failure")

                if step_id == bad_step:
                    return "not-a-dict"

                return {
                    "step": step_id,
                    "reviewed": True,
                }

            return run

        return BlockchainDeploymentExecutor(
            resolve_release=handler("resolve-release"),
            transfer_bootstrap=handler("transfer-bootstrap"),
            transfer_runtime=handler("transfer-runtime"),
            invoke_bootstrap=handler("invoke-bootstrap"),
            verify_runtime=handler("verify-runtime"),
            invoke_installer=handler("invoke-installer"),
            verify_installation=handler("verify-installation"),
        )

    def test_success_runs_all_steps_in_fixed_order(self):
        calls = []
        result = self.executor(calls).execute(self.request())

        self.assertTrue(result.ok)
        self.assertEqual(
            calls,
            list(BlockchainDeploymentExecutor.STEP_IDS),
        )
        self.assertEqual(
            [step.step_id for step in result.steps],
            list(BlockchainDeploymentExecutor.STEP_IDS),
        )
        self.assertTrue(all(step.ok for step in result.steps))

    def test_failure_stops_all_later_steps(self):
        calls = []

        result = self.executor(
            calls,
            fail_step="transfer-runtime",
        ).execute(self.request())

        self.assertFalse(result.ok)
        self.assertEqual(
            calls,
            [
                "resolve-release",
                "transfer-bootstrap",
                "transfer-runtime",
            ],
        )
        self.assertEqual(
            [step.step_id for step in result.steps],
            [
                "resolve-release",
                "transfer-bootstrap",
                "transfer-runtime",
            ],
        )
        self.assertEqual(result.steps[-1].status, "failed")
        self.assertIn("transfer-runtime", result.error)

    def test_invalid_step_evidence_fails_closed(self):
        calls = []

        result = self.executor(
            calls,
            bad_step="invoke-bootstrap",
        ).execute(self.request())

        self.assertFalse(result.ok)
        self.assertEqual(
            calls[-1],
            "invoke-bootstrap",
        )
        self.assertIn(
            "returned invalid evidence",
            result.error,
        )

    def test_result_is_structured_for_repository_result_data(self):
        calls = []
        result = self.executor(calls).execute(self.request())
        payload = result.to_dict()

        self.assertEqual(payload["status"], "completed")
        self.assertEqual(payload["providerId"], "btc")
        self.assertEqual(
            payload["storageTargetId"],
            "storage-main",
        )
        self.assertEqual(
            payload["targetAssetId"],
            "asset-test",
        )
        self.assertEqual(
            payload["correlationId"],
            "corr-test",
        )
        self.assertEqual(
            payload["approvedBy"],
            "approval-test",
        )
        self.assertEqual(len(payload["steps"]), 7)
        self.assertIn("durationMs", payload)

    def test_completed_step_evidence_flows_forward_only(self):
        seen = {}

        def resolve(request):
            return {"releaseId": "release-test"}

        def transfer_bootstrap(request, context, private_context):
            seen["bootstrap"] = context
            return {"bootstrapSha256": "a" * 64}

        def transfer_runtime(request, context, private_context):
            seen["runtime"] = context
            return {"runtimeSha256": "b" * 64}

        def generic(step):
            def run(request, context, private_context):
                seen[step] = context
                return {"ok": True}
            return run

        executor = BlockchainDeploymentExecutor(
            resolve_release=resolve,
            transfer_bootstrap=transfer_bootstrap,
            transfer_runtime=transfer_runtime,
            invoke_bootstrap=generic("invoke-bootstrap"),
            verify_runtime=generic("verify-runtime"),
            invoke_installer=generic("invoke-installer"),
            verify_installation=generic("verify-installation"),
        )

        result = executor.execute(self.request())

        self.assertTrue(result.ok)

        self.assertEqual(
            set(seen["bootstrap"]),
            {"resolve-release"},
        )
        self.assertEqual(
            set(seen["runtime"]),
            {
                "resolve-release",
                "transfer-bootstrap",
            },
        )

    def test_context_copy_prevents_step_from_mutating_history(self):
        observed = {}

        def resolve(request):
            return {"releaseId": "release-test"}

        def mutate(request, context, private_context):
            context["resolve-release"]["releaseId"] = "mutated"
            return {"ok": True}

        def inspect(request, context, private_context):
            observed.update(context["resolve-release"])
            return {"ok": True}

        executor = BlockchainDeploymentExecutor(
            resolve_release=resolve,
            transfer_bootstrap=mutate,
            transfer_runtime=inspect,
            invoke_bootstrap=lambda request, context, private_context: {"ok": True},
            verify_runtime=lambda request, context, private_context: {"ok": True},
            invoke_installer=lambda request, context, private_context: {"ok": True},
            verify_installation=lambda request, context, private_context: {"ok": True},
        )

        result = executor.execute(self.request())

        self.assertTrue(result.ok)
        self.assertEqual(
            observed["releaseId"],
            "release-test",
        )

    def test_missing_approval_identity_is_rejected_before_steps(self):
        calls = []
        request = DeploymentRequest(
            provider_id="btc",
            storage_target_id="storage-main",
            target_asset_id="asset-test",
            correlation_id="corr-test",
            approved_by="",
        )

        with self.assertRaises(BlockchainDeploymentError):
            self.executor(calls).execute(request)

        self.assertEqual(calls, [])

    def test_missing_correlation_is_rejected_before_steps(self):
        calls = []
        request = DeploymentRequest(
            provider_id="btc",
            storage_target_id="storage-main",
            target_asset_id="asset-test",
            correlation_id="",
            approved_by="approval-test",
        )

        with self.assertRaises(BlockchainDeploymentError):
            self.executor(calls).execute(request)

        self.assertEqual(calls, [])

    def test_private_state_flows_forward_but_is_not_persisted(self):
        private_release = object()
        observed = {}

        def resolve(request):
            return DeploymentStepOutput(
                evidence={"releaseId": "release-test"},
                private=private_release,
            )

        def transfer(request, context, private_context):
            observed["evidence"] = context
            observed["private"] = private_context
            return {"ok": True}

        executor = BlockchainDeploymentExecutor(
            resolve_release=resolve,
            transfer_bootstrap=transfer,
            transfer_runtime=lambda request, context, private_context: {"ok": True},
            invoke_bootstrap=lambda request, context, private_context: {"ok": True},
            verify_runtime=lambda request, context, private_context: {"ok": True},
            invoke_installer=lambda request, context, private_context: {"ok": True},
            verify_installation=lambda request, context, private_context: {"ok": True},
        )

        result = executor.execute(self.request())

        self.assertTrue(result.ok)
        self.assertIs(
            observed["private"]["resolve-release"],
            private_release,
        )
        self.assertEqual(
            observed["evidence"]["resolve-release"],
            {"releaseId": "release-test"},
        )

        payload = result.to_dict()
        encoded = repr(payload)
        self.assertNotIn(
            repr(private_release),
            encoded,
        )

    def test_private_context_mapping_is_read_only(self):
        observed = {}

        def resolve(request):
            return DeploymentStepOutput(
                evidence={"releaseId": "release-test"},
                private=object(),
            )

        def transfer(request, context, private_context):
            try:
                private_context["bad"] = object()
            except TypeError:
                observed["readOnly"] = True
            else:
                observed["readOnly"] = False

            return {"ok": True}

        executor = BlockchainDeploymentExecutor(
            resolve_release=resolve,
            transfer_bootstrap=transfer,
            transfer_runtime=lambda request, context, private_context: {"ok": True},
            invoke_bootstrap=lambda request, context, private_context: {"ok": True},
            verify_runtime=lambda request, context, private_context: {"ok": True},
            invoke_installer=lambda request, context, private_context: {"ok": True},
            verify_installation=lambda request, context, private_context: {"ok": True},
        )

        result = executor.execute(self.request())

        self.assertTrue(result.ok)
        self.assertTrue(observed["readOnly"])

    def test_path_in_evidence_fails_closed(self):
        from pathlib import Path

        calls = []

        def resolve(request):
            calls.append("resolve-release")
            return {
                "releaseId": "release-test",
                "badPath": Path("/private/path"),
            }

        executor = BlockchainDeploymentExecutor(
            resolve_release=resolve,
            transfer_bootstrap=lambda request, context, private_context: {"ok": True},
            transfer_runtime=lambda request, context, private_context: {"ok": True},
            invoke_bootstrap=lambda request, context, private_context: {"ok": True},
            verify_runtime=lambda request, context, private_context: {"ok": True},
            invoke_installer=lambda request, context, private_context: {"ok": True},
            verify_installation=lambda request, context, private_context: {"ok": True},
        )

        result = executor.execute(self.request())

        self.assertFalse(result.ok)
        self.assertEqual(calls, ["resolve-release"])
        self.assertIn(
            "non-JSON-safe evidence",
            result.error,
        )

    def test_private_path_is_allowed_and_never_serialized(self):
        from pathlib import Path

        private_path = Path("/private/reviewed/runtime.tar.gz")
        observed = {}

        def resolve(request):
            return DeploymentStepOutput(
                evidence={"releaseId": "release-test"},
                private=private_path,
            )

        def transfer(request, context, private_context):
            observed["path"] = private_context["resolve-release"]
            return {"ok": True}

        executor = BlockchainDeploymentExecutor(
            resolve_release=resolve,
            transfer_bootstrap=transfer,
            transfer_runtime=lambda request, context, private_context: {"ok": True},
            invoke_bootstrap=lambda request, context, private_context: {"ok": True},
            verify_runtime=lambda request, context, private_context: {"ok": True},
            invoke_installer=lambda request, context, private_context: {"ok": True},
            verify_installation=lambda request, context, private_context: {"ok": True},
        )

        result = executor.execute(self.request())

        self.assertTrue(result.ok)
        self.assertEqual(observed["path"], private_path)
        self.assertNotIn(
            str(private_path),
            repr(result.to_dict()),
        )


if __name__ == "__main__":
    unittest.main()
