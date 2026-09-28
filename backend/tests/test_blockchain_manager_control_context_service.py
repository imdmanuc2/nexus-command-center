from __future__ import annotations

import ssl
import unittest

from backend.services.blockchain_manager_control_context_service import (
    BlockchainManagerControlContext,
    BlockchainManagerControlContextService,
    safe_context_evidence,
)
from backend.services.blockchain_manager_control_endpoint_service import (
    BlockchainManagerControlEndpoint,
)


SSL_CONTEXT = ssl.create_default_context()


class FakeEndpointService:
    def __init__(self, result):
        self.result = result
        self.calls = []

    def resolve(
        self,
        *,
        target_asset_id: str,
    ):
        self.calls.append(
            target_asset_id
        )

        return self.result


class BlockchainManagerControlContextTests(
    unittest.TestCase
):
    def endpoint(self):
        return BlockchainManagerControlEndpoint(
            target_asset_id="asset-154",
            endpoint_id="endpoint-bm-154",
            base_url="https://192.168.1.154:8571",
            protocol="https",
            host="192.168.1.154",
            port=8571,
            tls_enabled=True,
        )

    def test_resolves_typed_private_context(
        self,
    ):
        endpoint_service = (
            FakeEndpointService(
                self.endpoint()
            )
        )

        captured = {}

        def load_credential(
            *,
            target_asset_id,
        ):
            captured[
                "target_asset_id"
            ] = target_asset_id

            return "super-secret-token"

        service = (
            BlockchainManagerControlContextService(
                tls_context_loader=(
                    lambda **_kwargs: SSL_CONTEXT
                ),
                endpoint_service=(
                    endpoint_service
                ),
                credential_loader=(
                    load_credential
                ),
            )
        )

        result = service.resolve(
            target_asset_id="asset-154"
        )

        self.assertIsInstance(
            result,
            BlockchainManagerControlContext,
        )

        self.assertEqual(
            result.target_asset_id,
            "asset-154",
        )

        self.assertEqual(
            result.endpoint_id,
            "endpoint-bm-154",
        )

        self.assertEqual(
            result.endpoint,
            "https://192.168.1.154:8571",
        )

        self.assertEqual(
            result.token,
            "super-secret-token",
        )

        self.assertEqual(
            endpoint_service.calls,
            ["asset-154"],
        )

        self.assertEqual(
            captured[
                "target_asset_id"
            ],
            "asset-154",
        )

    def test_endpoint_resolves_before_credential(
        self,
    ):
        order = []

        class EndpointService:
            def resolve(
                self,
                *,
                target_asset_id,
            ):
                order.append(
                    "endpoint"
                )

                return (
                    BlockchainManagerControlEndpoint(
                        target_asset_id=(
                            target_asset_id
                        ),
                        endpoint_id="endpoint",
                        base_url=(
                            "https://manager:8571"
                        ),
                        protocol="https",
                        host="manager",
                        port=8571,
                        tls_enabled=True,
                    )
                )

        def credential_loader(
            *,
            target_asset_id,
        ):
            order.append(
                "credential"
            )

            return "secret"

        service = (
            BlockchainManagerControlContextService(
                tls_context_loader=(
                    lambda **_kwargs: SSL_CONTEXT
                ),
                endpoint_service=EndpointService(),
                credential_loader=credential_loader,
            )
        )

        service.resolve(
            target_asset_id="asset-154"
        )

        self.assertEqual(
            order,
            [
                "endpoint",
                "credential",
            ],
        )

    def test_endpoint_failure_prevents_credential_load(
        self,
    ):
        called = []

        class EndpointService:
            def resolve(
                self,
                *,
                target_asset_id,
            ):
                raise ValueError(
                    "endpoint missing"
                )

        def credential_loader(
            *,
            target_asset_id,
        ):
            called.append(
                target_asset_id
            )
            return "secret"

        service = (
            BlockchainManagerControlContextService(
                tls_context_loader=(
                    lambda **_kwargs: SSL_CONTEXT
                ),
                endpoint_service=EndpointService(),
                credential_loader=credential_loader,
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "endpoint missing",
        ):
            service.resolve(
                target_asset_id="asset-154"
            )

        self.assertEqual(
            called,
            [],
        )

    def test_invalid_endpoint_type_fails_closed(
        self,
    ):
        called = []

        def credential_loader(
            *,
            target_asset_id,
        ):
            called.append(
                target_asset_id
            )
            return "secret"

        service = (
            BlockchainManagerControlContextService(
                tls_context_loader=(
                    lambda **_kwargs: SSL_CONTEXT
                ),
                endpoint_service=(
                    FakeEndpointService(
                        {
                            "endpoint":
                                "http://bad"
                        }
                    )
                ),
                credential_loader=credential_loader,
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "invalid result",
        ):
            service.resolve(
                target_asset_id="asset-154"
            )

        self.assertEqual(
            called,
            [],
        )

    def test_endpoint_target_mismatch_fails_before_secret(
        self,
    ):
        endpoint = self.endpoint()

        endpoint = (
            BlockchainManagerControlEndpoint(
                target_asset_id="asset-other",
                endpoint_id=endpoint.endpoint_id,
                base_url=endpoint.base_url,
                protocol=endpoint.protocol,
                host=endpoint.host,
                port=endpoint.port,
                tls_enabled=endpoint.tls_enabled,
            )
        )

        called = []

        def credential_loader(
            *,
            target_asset_id,
        ):
            called.append(
                target_asset_id
            )
            return "secret"

        service = (
            BlockchainManagerControlContextService(
                tls_context_loader=(
                    lambda **_kwargs: SSL_CONTEXT
                ),
                endpoint_service=(
                    FakeEndpointService(
                        endpoint
                    )
                ),
                credential_loader=credential_loader,
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "target identity mismatch",
        ):
            service.resolve(
                target_asset_id="asset-154"
            )

        self.assertEqual(
            called,
            [],
        )

    def test_missing_credential_fails_closed(
        self,
    ):
        service = (
            BlockchainManagerControlContextService(
                tls_context_loader=(
                    lambda **_kwargs: SSL_CONTEXT
                ),
                endpoint_service=(
                    FakeEndpointService(
                        self.endpoint()
                    )
                ),
                credential_loader=(
                    lambda **_kwargs: ""
                ),
            )
        )

        with self.assertRaisesRegex(
            ValueError,
            "credential is missing",
        ):
            service.resolve(
                target_asset_id="asset-154"
            )

    def test_private_context_repr_excludes_token(
        self,
    ):
        context = BlockchainManagerControlContext(
            target_asset_id="asset-154",
            endpoint_id="endpoint-bm-154",
            endpoint="https://192.0.2.154:8571",
            protocol="https",
            ssl_context=SSL_CONTEXT,
            token="super-secret-control-token",
        )

        rendered = repr(
            context
        )

        self.assertNotIn(
            "super-secret-control-token",
            rendered,
        )

        self.assertNotIn(
            "token=",
            rendered,
        )

        self.assertIn(
            "asset-154",
            rendered,
        )

        self.assertIn(
            "endpoint-bm-154",
            rendered,
        )

    def test_safe_evidence_contains_no_secret(
        self,
    ):
        context = (
            BlockchainManagerControlContext(
                target_asset_id="asset-154",
                endpoint_id="endpoint-bm-154",
                endpoint=(
                    "https://192.168.1.154:8571"
                ),
                protocol="https",
                ssl_context=SSL_CONTEXT,
                token="super-secret-token",
            )
        )

        evidence = safe_context_evidence(
            context
        )

        self.assertEqual(
            evidence,
            {
                "targetAssetId":
                    "asset-154",
                "endpointId":
                    "endpoint-bm-154",
                "transport":
                    "https",
                "authority":
                    "blockchain-manager",
            },
        )

        rendered = repr(
            evidence
        )

        self.assertNotIn(
            "super-secret-token",
            rendered,
        )

        self.assertNotIn(
            "192.168.1.154",
            rendered,
        )

    def test_safe_evidence_rejects_wrong_type(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "Invalid Blockchain Manager",
        ):
            safe_context_evidence(
                object()
            )


if __name__ == "__main__":
    unittest.main()
