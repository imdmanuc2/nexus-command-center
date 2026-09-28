from __future__ import annotations

import io
import json
import unittest
from unittest.mock import MagicMock, patch

from backend.api import server


class FakeHeaders:
    def __init__(self, values=None):
        self.values = dict(values or {})

    def get(self, key, default=None):
        return self.values.get(key, default)


def handler(
    *,
    path,
    payload=None,
):
    value = object.__new__(
        server.NexusHandler
    )

    value.path = path

    body = b""

    if payload is not None:
        body = json.dumps(
            payload
        ).encode("utf-8")

    value.headers = FakeHeaders({
        "Content-Length": str(len(body)),
    })
    value.rfile = io.BytesIO(body)
    value.wfile = io.BytesIO()

    value.send_response = MagicMock()
    value.send_header = MagicMock()
    value.end_headers = MagicMock()

    return value


def response_json(value):
    raw = value.wfile.getvalue()

    if not raw:
        return None

    return json.loads(
        raw.decode("utf-8")
    )


class DeploymentAuthorityHttpTests(
    unittest.TestCase
):
    @patch(
        "backend.api.server."
        "DeploymentAuthorityManagementService"
    )
    def test_lists_storage_candidates(
        self,
        service_type,
    ):
        service = service_type.return_value

        service.list_storage_candidates.return_value = {
            "status": "ok",
            "targetAssetId": "asset-managed-1",
            "candidates": [],
        }

        value = handler(
            path=(
                "/api/platform/"
                "deployment-authority/"
                "storage-candidates"
                "?targetAssetId=asset-managed-1"
            ),
        )

        server.NexusHandler.do_GET(value)

        service.list_storage_candidates.assert_called_once_with(
            asset_id="asset-managed-1",
        )

        value.send_response.assert_called_once_with(
            200
        )

    @patch(
        "backend.api.server."
        "DeploymentAuthorityManagementService"
    )
    def test_storage_candidates_require_target(
        self,
        service_type,
    ):
        value = handler(
            path=(
                "/api/platform/"
                "deployment-authority/"
                "storage-candidates"
            ),
        )

        server.NexusHandler.do_GET(value)

        service_type.assert_not_called()
        value.send_response.assert_called_once_with(
            400
        )

    @patch(
        "backend.api.server."
        "DeploymentAuthorityManagementService"
    )
    def test_platform_classification(
        self,
        service_type,
    ):
        service = service_type.return_value

        service.classify_deployment_platform.return_value = {
            "status": "ok",
            "targetAssetId": "asset-managed-1",
            "deploymentPlatformId": "umbrel",
        }

        value = handler(
            path=(
                "/api/platform/"
                "deployment-authority/platform"
            ),
            payload={
                "targetAssetId": "asset-managed-1",
                "platformId": "umbrel",
                "actorId": "operator-1",
                "execute": False,
            },
        )

        server.NexusHandler.do_POST(value)

        service.classify_deployment_platform.assert_called_once_with(
            asset_id="asset-managed-1",
            platform_id="umbrel",
            actor_id="operator-1",
            execute=False,
        )

        value.send_response.assert_called_once_with(
            200
        )

    @patch(
        "backend.api.server."
        "DeploymentAuthorityManagementService"
    )
    def test_platform_requires_actor(
        self,
        service_type,
    ):
        value = handler(
            path=(
                "/api/platform/"
                "deployment-authority/platform"
            ),
            payload={
                "targetAssetId": "asset-managed-1",
                "platformId": "umbrel",
            },
        )

        server.NexusHandler.do_POST(value)

        service_type.assert_not_called()
        value.send_response.assert_called_once_with(
            400
        )

    @patch(
        "backend.api.server."
        "DeploymentAuthorityManagementService"
    )
    def test_platform_rejects_unknown_fields(
        self,
        service_type,
    ):
        value = handler(
            path=(
                "/api/platform/"
                "deployment-authority/platform"
            ),
            payload={
                "targetAssetId": "asset-managed-1",
                "platformId": "umbrel",
                "actorId": "operator-1",
                "mountPath": "/caller/controlled",
            },
        )

        server.NexusHandler.do_POST(value)

        service_type.assert_not_called()
        value.send_response.assert_called_once_with(
            400
        )

    @patch(
        "backend.api.server."
        "DeploymentAuthorityManagementService"
    )
    def test_storage_enrollment(
        self,
        service_type,
    ):
        service = service_type.return_value

        service.enroll_storage.return_value = {
            "status": "ok",
            "targetAssetId": "asset-managed-1",
            "storageTargetId": "storage-1",
        }

        value = handler(
            path=(
                "/api/platform/"
                "deployment-authority/storage"
            ),
            payload={
                "targetAssetId": "asset-managed-1",
                "storageAssetId": "asset-storage-1",
                "actorId": "operator-1",
                "approved": True,
                "execute": False,
            },
        )

        server.NexusHandler.do_POST(value)

        service.enroll_storage.assert_called_once_with(
            asset_id="asset-managed-1",
            storage_asset_id="asset-storage-1",
            actor_id="operator-1",
            approved=True,
            execute=False,
        )

        value.send_response.assert_called_once_with(
            200
        )

    @patch(
        "backend.api.server."
        "DeploymentAuthorityManagementService"
    )
    def test_storage_requires_candidate(
        self,
        service_type,
    ):
        value = handler(
            path=(
                "/api/platform/"
                "deployment-authority/storage"
            ),
            payload={
                "targetAssetId": "asset-managed-1",
                "actorId": "operator-1",
            },
        )

        server.NexusHandler.do_POST(value)

        service_type.assert_not_called()
        value.send_response.assert_called_once_with(
            400
        )

    @patch(
        "backend.api.server."
        "DeploymentAuthorityManagementService"
    )
    def test_storage_rejects_filesystem_authority(
        self,
        service_type,
    ):
        value = handler(
            path=(
                "/api/platform/"
                "deployment-authority/storage"
            ),
            payload={
                "targetAssetId": "asset-managed-1",
                "storageAssetId": "asset-storage-1",
                "actorId": "operator-1",
                "filesystem": "ext4",
            },
        )

        server.NexusHandler.do_POST(value)

        service_type.assert_not_called()
        value.send_response.assert_called_once_with(
            400
        )

    @patch(
        "backend.api.server."
        "DeploymentAuthorityManagementService"
    )
    def test_service_value_error_maps_to_400(
        self,
        service_type,
    ):
        service = service_type.return_value

        service.classify_deployment_platform.side_effect = (
            ValueError("Unsupported platform.")
        )

        value = handler(
            path=(
                "/api/platform/"
                "deployment-authority/platform"
            ),
            payload={
                "targetAssetId": "asset-managed-1",
                "platformId": "invalid",
                "actorId": "operator-1",
            },
        )

        server.NexusHandler.do_POST(value)

        value.send_response.assert_called_once_with(
            400
        )

        self.assertEqual(
            response_json(value)["status"],
            "error",
        )

    @patch(
        "backend.api.server."
        "DeploymentAuthorityManagementService"
    )
    def test_unexpected_service_failure_is_sanitized(
        self,
        service_type,
    ):
        service = service_type.return_value

        service.enroll_storage.side_effect = (
            RuntimeError(
                "private database detail"
            )
        )

        value = handler(
            path=(
                "/api/platform/"
                "deployment-authority/storage"
            ),
            payload={
                "targetAssetId": "asset-managed-1",
                "storageAssetId": "asset-storage-1",
                "actorId": "operator-1",
            },
        )

        server.NexusHandler.do_POST(value)

        value.send_response.assert_called_once_with(
            500
        )

        result = response_json(value)

        self.assertEqual(
            result["error"],
            "Deployment authority request failed.",
        )

        self.assertNotIn(
            "private database detail",
            json.dumps(result),
        )


    @patch(
        "backend.api.server."
        "DeploymentAuthorityManagementService"
    )
    def test_platform_execute_true_is_explicit(
        self,
        service_type,
    ):
        service = service_type.return_value

        service.classify_deployment_platform.return_value = {
            "status": "classified",
        }

        value = handler(
            path=(
                "/api/platform/"
                "deployment-authority/platform"
            ),
            payload={
                "targetAssetId": "asset-managed-1",
                "platformId": "umbrel",
                "actorId": "operator-1",
                "execute": True,
            },
        )

        server.NexusHandler.do_POST(value)

        service.classify_deployment_platform.assert_called_once_with(
            asset_id="asset-managed-1",
            platform_id="umbrel",
            actor_id="operator-1",
            execute=True,
        )

        value.send_response.assert_called_once_with(
            200
        )

    @patch(
        "backend.api.server."
        "DeploymentAuthorityManagementService"
    )
    def test_platform_execute_must_be_boolean(
        self,
        service_type,
    ):
        value = handler(
            path=(
                "/api/platform/"
                "deployment-authority/platform"
            ),
            payload={
                "targetAssetId": "asset-managed-1",
                "platformId": "umbrel",
                "actorId": "operator-1",
                "execute": "true",
            },
        )

        server.NexusHandler.do_POST(value)

        service_type.return_value.classify_deployment_platform.assert_not_called()

        value.send_response.assert_called_once_with(
            400
        )

    @patch(
        "backend.api.server."
        "DeploymentAuthorityManagementService"
    )
    def test_storage_defaults_to_unapproved_plan(
        self,
        service_type,
    ):
        service = service_type.return_value

        service.enroll_storage.return_value = {
            "status": "approval-required",
            "approved": False,
            "executionPerformed": False,
        }

        value = handler(
            path=(
                "/api/platform/"
                "deployment-authority/storage"
            ),
            payload={
                "targetAssetId": "asset-managed-1",
                "storageAssetId": "asset-storage-1",
                "actorId": "operator-1",
            },
        )

        server.NexusHandler.do_POST(value)

        service.enroll_storage.assert_called_once_with(
            asset_id="asset-managed-1",
            storage_asset_id="asset-storage-1",
            actor_id="operator-1",
            approved=False,
            execute=False,
        )

        value.send_response.assert_called_once_with(
            200
        )

    @patch(
        "backend.api.server."
        "DeploymentAuthorityManagementService"
    )
    def test_storage_execute_requires_explicit_booleans(
        self,
        service_type,
    ):
        service = service_type.return_value

        service.enroll_storage.return_value = {
            "status": "enrolled",
            "approved": True,
            "executionPerformed": True,
        }

        value = handler(
            path=(
                "/api/platform/"
                "deployment-authority/storage"
            ),
            payload={
                "targetAssetId": "asset-managed-1",
                "storageAssetId": "asset-storage-1",
                "actorId": "operator-1",
                "approved": True,
                "execute": True,
            },
        )

        server.NexusHandler.do_POST(value)

        service.enroll_storage.assert_called_once_with(
            asset_id="asset-managed-1",
            storage_asset_id="asset-storage-1",
            actor_id="operator-1",
            approved=True,
            execute=True,
        )

        value.send_response.assert_called_once_with(
            200
        )

    @patch(
        "backend.api.server."
        "DeploymentAuthorityManagementService"
    )
    def test_storage_boolean_strings_are_rejected(
        self,
        service_type,
    ):
        value = handler(
            path=(
                "/api/platform/"
                "deployment-authority/storage"
            ),
            payload={
                "targetAssetId": "asset-managed-1",
                "storageAssetId": "asset-storage-1",
                "actorId": "operator-1",
                "approved": "true",
                "execute": False,
            },
        )

        server.NexusHandler.do_POST(value)

        service_type.return_value.enroll_storage.assert_not_called()

        value.send_response.assert_called_once_with(
            400
        )


if __name__ == "__main__":
    unittest.main()
