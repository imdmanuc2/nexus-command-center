from __future__ import annotations

import json
import ssl
import unittest
from urllib.error import HTTPError
from io import BytesIO

from backend.transports.blockchain_manager_control import (
    BlockchainManagerControlError,
    BlockchainManagerControlTransport,
    BlockchainManagerInstallRequest,
)

SSL_CONTEXT = ssl.create_default_context()


class FakeResponse:
    def __init__(
        self,
        payload,
        status=200,
    ):
        self.status = status
        self._body = json.dumps(
            payload
        ).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(
        self,
        exc_type,
        exc,
        traceback,
    ):
        return False


class BlockchainManagerControlTests(
    unittest.TestCase
):
    def test_posts_minimal_install_contract(self):
        captured = {}

        def opener(request, timeout, context):
            captured["url"] = request.full_url
            captured["timeout"] = timeout
            captured["context"] = context
            captured["headers"] = dict(
                request.header_items()
            )
            captured["body"] = json.loads(
                request.data.decode("utf-8")
            )

            return FakeResponse({
                "operationId":
                    "operation-1",
                "status":
                    "succeeded",
                "result": {},
                "verification": {
                    "verified": True,
                },
                "error": None,
            })

        transport = (
            BlockchainManagerControlTransport(
                opener=opener
            )
        )

        result = transport.install(
            endpoint="https://manager.local:8571",
            token="control-secret",
            ssl_context=SSL_CONTEXT,
            request=BlockchainManagerInstallRequest(
                provider_id="bitcoin-mainnet",
                storage_target_id="storage-1",
            ),
            timeout_seconds=30,
        )

        self.assertEqual(
            captured["url"],
            "https://manager.local:8571"
            "/api/nexus/install/execute",
        )

        self.assertIs(
            captured["context"],
            SSL_CONTEXT,
        )

        self.assertEqual(
            captured["body"],
            {
                "providerId":
                    "bitcoin-mainnet",
                "storageTargetId":
                    "storage-1",
            },
        )

        self.assertEqual(
            set(captured["body"]),
            {
                "providerId",
                "storageTargetId",
            },
        )

        self.assertEqual(
            captured["headers"][
                "Authorization"
            ],
            "Bearer control-secret",
        )

        self.assertEqual(
            result.operation_id,
            "operation-1",
        )

        self.assertTrue(
            result.verified
        )

    def test_secret_is_not_in_body(self):
        captured = {}

        def opener(request, timeout, context):
            captured["body"] = (
                request.data.decode(
                    "utf-8"
                )
            )

            return FakeResponse({
                "operationId":
                    "operation-2",
                "status":
                    "succeeded",
                "verification": {
                    "verified": True,
                },
            })

        transport = (
            BlockchainManagerControlTransport(
                opener=opener
            )
        )

        transport.install(
            endpoint="https://manager.local:8571",
            token="super-secret-token",
            ssl_context=SSL_CONTEXT,
            request=BlockchainManagerInstallRequest(
                provider_id="monero-mainnet",
                storage_target_id="storage-xmr",
            ),
        )

        self.assertNotIn(
            "super-secret-token",
            captured["body"],
        )

    def test_rejects_invalid_provider(self):
        transport = (
            BlockchainManagerControlTransport(
                opener=lambda *_a, **_k: None
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "Invalid provider_id",
        ):
            transport.install(
                endpoint="https://manager.local",
                token="token",
                ssl_context=SSL_CONTEXT,
                request=(
                    BlockchainManagerInstallRequest(
                        provider_id="../bad",
                        storage_target_id="storage-1",
                    )
                ),
            )

    def test_rejects_invalid_storage_target(self):
        transport = (
            BlockchainManagerControlTransport(
                opener=lambda *_a, **_k: None
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "Invalid storage_target_id",
        ):
            transport.install(
                endpoint="https://manager.local",
                token="token",
                ssl_context=SSL_CONTEXT,
                request=(
                    BlockchainManagerInstallRequest(
                        provider_id="bitcoin-mainnet",
                        storage_target_id="../bad path",
                    )
                ),
            )

    def test_requires_control_token(self):
        transport = (
            BlockchainManagerControlTransport(
                opener=lambda *_a, **_k: None
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "control token is required",
        ):
            transport.install(
                endpoint="https://manager.local",
                token="",
                ssl_context=SSL_CONTEXT,
                request=(
                    BlockchainManagerInstallRequest(
                        provider_id="bitcoin-mainnet",
                        storage_target_id="storage-1",
                    )
                ),
            )

    def test_requires_https_endpoint(self):
        transport = (
            BlockchainManagerControlTransport(
                opener=lambda *_a, **_k: None
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "must use HTTPS",
        ):
            transport.install(
                endpoint="http://manager.local",
                token="token",
                ssl_context=SSL_CONTEXT,
                request=(
                    BlockchainManagerInstallRequest(
                        provider_id="bitcoin-mainnet",
                        storage_target_id="storage-1",
                    )
                ),
            )

    def test_fails_closed_on_http_unauthorized(self):
        def opener(request, timeout, context):
            raise HTTPError(
                request.full_url,
                401,
                "Unauthorized",
                {},
                BytesIO(
                    json.dumps({
                        "error":
                            "nexus-control-authentication-required"
                    }).encode("utf-8")
                ),
            )

        transport = (
            BlockchainManagerControlTransport(
                opener=opener
            )
        )

        with self.assertRaisesRegex(
            BlockchainManagerControlError,
            "401",
        ):
            transport.install(
                endpoint="https://manager.local",
                token="wrong",
                ssl_context=SSL_CONTEXT,
                request=(
                    BlockchainManagerInstallRequest(
                        provider_id="bitcoin-mainnet",
                        storage_target_id="storage-1",
                    )
                ),
            )

    def test_requires_operation_id(self):
        transport = (
            BlockchainManagerControlTransport(
                opener=lambda *_a, **_k:
                    FakeResponse({
                        "status":
                            "succeeded",
                        "verification": {
                            "verified": True,
                        },
                    })
            )
        )

        with self.assertRaisesRegex(
            BlockchainManagerControlError,
            "operationId",
        ):
            transport.install(
                endpoint="https://manager.local",
                token="token",
                ssl_context=SSL_CONTEXT,
                request=(
                    BlockchainManagerInstallRequest(
                        provider_id="bitcoin-mainnet",
                        storage_target_id="storage-1",
                    )
                ),
            )

    def test_requires_verified_result(self):
        transport = (
            BlockchainManagerControlTransport(
                opener=lambda *_a, **_k:
                    FakeResponse({
                        "operationId":
                            "operation-3",
                        "status":
                            "succeeded",
                        "verification": {
                            "verified": False,
                        },
                    })
            )
        )

        with self.assertRaisesRegex(
            BlockchainManagerControlError,
            "not verified",
        ):
            transport.install(
                endpoint="https://manager.local",
                token="token",
                ssl_context=SSL_CONTEXT,
                request=(
                    BlockchainManagerInstallRequest(
                        provider_id="bitcoin-mainnet",
                        storage_target_id="storage-1",
                    )
                ),
            )


if __name__ == "__main__":
    unittest.main()
