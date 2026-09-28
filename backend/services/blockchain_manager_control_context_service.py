"""Resolve private Nexus -> Blockchain Manager machine-control context.

The returned context contains the bearer credential and therefore must
remain execution-private. It must never be persisted into:

- operation parameters
- operation evidence
- CMDB metadata
- audit payloads
- API responses
- logs
"""

from __future__ import annotations

from dataclasses import dataclass, field
import ssl
from typing import Callable

from backend.services import (
    blockchain_manager_control_credential_service,
)
from backend.services.blockchain_manager_control_endpoint_service import (
    BlockchainManagerControlEndpoint,
    BlockchainManagerControlEndpointService,
)
from backend.services import (
    blockchain_manager_control_tls_trust_service,
)


@dataclass(frozen=True, slots=True)
class BlockchainManagerControlContext:
    target_asset_id: str
    endpoint_id: str
    endpoint: str
    protocol: str
    ssl_context: ssl.SSLContext = field(repr=False)
    token: str = field(repr=False)


class BlockchainManagerControlContextService:
    def __init__(
        self,
        *,
        endpoint_service: (
            BlockchainManagerControlEndpointService
            | None
        ) = None,
        tls_context_loader: Callable[
            ..., ssl.SSLContext
        ] = (
            blockchain_manager_control_tls_trust_service
            .create_ssl_context
        ),
        credential_loader: Callable[..., str] = (
            blockchain_manager_control_credential_service
            .load_credential
        ),
    ) -> None:
        self._endpoint_service = (
            endpoint_service
            or BlockchainManagerControlEndpointService()
        )

        self._tls_context_loader = (
            tls_context_loader
        )

        self._credential_loader = (
            credential_loader
        )

    def resolve(
        self,
        *,
        target_asset_id: str,
    ) -> BlockchainManagerControlContext:
        endpoint = (
            self._endpoint_service.resolve(
                target_asset_id=target_asset_id,
            )
        )

        if not isinstance(
            endpoint,
            BlockchainManagerControlEndpoint,
        ):
            raise ValueError(
                "Blockchain Manager endpoint "
                "resolver returned invalid result"
            )

        if (
            endpoint.target_asset_id
            != target_asset_id
        ):
            raise ValueError(
                "Blockchain Manager control "
                "context target identity mismatch"
            )

        ssl_context = (
            self._tls_context_loader(
                target_asset_id=target_asset_id,
            )
        )

        if not isinstance(
            ssl_context,
            ssl.SSLContext,
        ):
            raise ValueError(
                "Blockchain Manager TLS trust "
                "resolver returned invalid context"
            )

        token = str(
            self._credential_loader(
                target_asset_id=target_asset_id,
            )
            or ""
        ).strip()

        if not token:
            raise ValueError(
                "Blockchain Manager control "
                "credential is missing"
            )

        return BlockchainManagerControlContext(
            target_asset_id=target_asset_id,
            endpoint_id=endpoint.endpoint_id,
            endpoint=endpoint.base_url,
            protocol=endpoint.protocol,
            ssl_context=ssl_context,
            token=token,
        )


def safe_context_evidence(
    context: BlockchainManagerControlContext,
) -> dict[str, str]:
    """Return only non-secret control-routing evidence."""

    if not isinstance(
        context,
        BlockchainManagerControlContext,
    ):
        raise ValueError(
            "Invalid Blockchain Manager control context"
        )

    return {
        "targetAssetId":
            context.target_asset_id,
        "endpointId":
            context.endpoint_id,
        "transport":
            context.protocol,
        "authority":
            "blockchain-manager",
    }
