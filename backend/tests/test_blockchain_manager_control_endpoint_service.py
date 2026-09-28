from __future__ import annotations

import unittest

from backend.services.blockchain_manager_control_endpoint_service import (
    BlockchainManagerControlEndpointService,
)


_UNSET = object()


class BlockchainManagerControlEndpointTests(
    unittest.TestCase
):
    def asset(self):
        return {
            "id": "asset-154",
            "managed": True,
            "deploymentPlatformId":
                "umbrel",
        }

    def endpoint(self):
        return {
            "endpoint_id":
                "endpoint-bm-154",
            "subject_type":
                "asset",
            "subject_id":
                "asset-154",
            "service_type":
                "blockchain-manager-control",
            "protocol":
                "https",
            "host":
                "192.168.1.154",
            "port":
                8571,
            "path":
                "",
            "tls_enabled":
                True,
            "status":
                "healthy",
            "metadata":
                {},
        }

    def service(
        self,
        *,
        asset=_UNSET,
        endpoints=_UNSET,
    ):
        if asset is _UNSET:
            resolved_response = {
                "status": "ok",
                "asset": self.asset(),
            }
        elif asset is None:
            resolved_response = None
        else:
            resolved_response = {
                "status": "ok",
                "asset": asset,
            }

        resolved_endpoints = (
            [self.endpoint()]
            if endpoints is _UNSET
            else endpoints
        )

        return BlockchainManagerControlEndpointService(
            asset_loader=(
                lambda _asset_id:
                    resolved_response
            ),
            endpoint_loader=(
                lambda **_kwargs:
                    resolved_endpoints
            ),
        )

    def test_resolves_exact_asset_bound_endpoint(
        self,
    ):
        result = self.service().resolve(
            target_asset_id="asset-154"
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
            result.base_url,
            "https://192.168.1.154:8571",
        )

    def test_requires_exactly_one_endpoint(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "Exactly one",
        ):
            self.service(
                endpoints=[]
            ).resolve(
                target_asset_id="asset-154"
            )

        with self.assertRaisesRegex(
            ValueError,
            "Exactly one",
        ):
            self.service(
                endpoints=[
                    self.endpoint(),
                    self.endpoint(),
                ]
            ).resolve(
                target_asset_id="asset-154"
            )

    def test_missing_cmdb_asset_fails_closed(
        self,
    ):
        with self.assertRaisesRegex(
            ValueError,
            "invalid Blockchain Manager control target response",
        ):
            self.service(
                asset=None
            ).resolve(
                target_asset_id="asset-154"
            )

    def test_target_identity_mismatch_fails_closed(
        self,
    ):
        asset = self.asset()
        asset["id"] = "asset-other"

        with self.assertRaisesRegex(
            ValueError,
            "identity mismatch",
        ):
            self.service(
                asset=asset
            ).resolve(
                target_asset_id="asset-154"
            )

    def test_unmanaged_asset_fails_closed(
        self,
    ):
        asset = self.asset()
        asset["managed"] = False

        with self.assertRaisesRegex(
            ValueError,
            "managed CMDB asset",
        ):
            self.service(
                asset=asset
            ).resolve(
                target_asset_id="asset-154"
            )

    def test_non_ok_cmdb_status_fails_closed(
        self,
    ):
        service = BlockchainManagerControlEndpointService(
            asset_loader=(
                lambda _asset_id: {
                    "status": "not_found",
                    "asset": None,
                }
            ),
            endpoint_loader=(
                lambda **_kwargs: [
                    self.endpoint()
                ]
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "does not exist in CMDB",
        ):
            service.resolve(
                target_asset_id="asset-154"
            )

    def test_missing_cmdb_asset_payload_fails_closed(
        self,
    ):
        service = BlockchainManagerControlEndpointService(
            asset_loader=(
                lambda _asset_id: {
                    "status": "ok",
                    "asset": None,
                }
            ),
            endpoint_loader=(
                lambda **_kwargs: [
                    self.endpoint()
                ]
            ),
        )

        with self.assertRaisesRegex(
            ValueError,
            "invalid Blockchain Manager control target asset",
        ):
            service.resolve(
                target_asset_id="asset-154"
            )

    def test_non_umbrel_asset_fails_closed(
        self,
    ):
        asset = self.asset()
        asset[
            "deploymentPlatformId"
        ] = "linux"

        with self.assertRaisesRegex(
            ValueError,
            "Umbrel",
        ):
            self.service(
                asset=asset
            ).resolve(
                target_asset_id="asset-154"
            )

    def test_endpoint_target_mismatch_fails_closed(
        self,
    ):
        endpoint = self.endpoint()
        endpoint[
            "subject_id"
        ] = "asset-other"

        with self.assertRaisesRegex(
            ValueError,
            "target identity mismatch",
        ):
            self.service(
                endpoints=[endpoint]
            ).resolve(
                target_asset_id="asset-154"
            )

    def test_service_type_mismatch_fails_closed(
        self,
    ):
        endpoint = self.endpoint()
        endpoint[
            "service_type"
        ] = "other-service"

        with self.assertRaisesRegex(
            ValueError,
            "service type mismatch",
        ):
            self.service(
                endpoints=[endpoint]
            ).resolve(
                target_asset_id="asset-154"
            )

    def test_plain_http_control_fails_closed(self):
        endpoint = self.endpoint()
        endpoint["protocol"] = "http"
        endpoint["tls_enabled"] = False

        with self.assertRaisesRegex(
            ValueError,
            "authenticated HTTPS",
        ):
            self.service(
                endpoints=[endpoint]
            ).resolve(
                target_asset_id="asset-154"
            )

    def test_https_without_tls_flag_fails_closed(self):
        endpoint = self.endpoint()
        endpoint["tls_enabled"] = False

        with self.assertRaisesRegex(
            ValueError,
            "authenticated HTTPS",
        ):
            self.service(
                endpoints=[endpoint]
            ).resolve(
                target_asset_id="asset-154"
            )

    def test_registered_path_must_be_service_root(
        self,
    ):
        endpoint = self.endpoint()
        endpoint[
            "path"
        ] = "/api/nexus"

        with self.assertRaisesRegex(
            ValueError,
            "service root",
        ):
            self.service(
                endpoints=[endpoint]
            ).resolve(
                target_asset_id="asset-154"
            )

    def test_ipv6_endpoint_is_bracketed(self):
        endpoint = self.endpoint()
        endpoint["host"] = "2001:db8::154"

        result = self.service(
            endpoints=[endpoint]
        ).resolve(
            target_asset_id="asset-154"
        )

        self.assertEqual(
            result.base_url,
            "https://[2001:db8::154]:8571",
        )


if __name__ == "__main__":
    unittest.main()
