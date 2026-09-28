"""Execute an approved blockchain install through Blockchain Manager.

This service is intentionally transport-oriented and execution-private.

Nexus supplies only:
- target CMDB asset identity
- provider identity
- approved storage target identity

The Blockchain Manager target owns:
- app/runtime identity
- RPC credentials
- ports
- confirmation material
- Umbrel filesystem mutation
- Umbrel lifecycle operations

The bearer token and endpoint address must never be projected into
durable operation evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Callable

from backend.services.blockchain_manager_control_context_service import (
    BlockchainManagerControlContext,
    BlockchainManagerControlContextService,
    safe_context_evidence,
)
from backend.transports.blockchain_manager_control import (
    BlockchainManagerControlTransport,
    BlockchainManagerInstallRequest,
    BlockchainManagerInstallResult,
)


_PROVIDER_RE = re.compile(
    r"^[a-z0-9][a-z0-9-]{0,63}$"
)

_STORAGE_RE = re.compile(
    r"^[A-Za-z0-9_.:-]{1,128}$"
)


@dataclass(frozen=True, slots=True)
class BlockchainManagerInstallExecutionRequest:
    target_asset_id: str
    provider_id: str
    storage_target_id: str
    storage_source: str
    storage_filesystem: str


@dataclass(frozen=True, slots=True)
class BlockchainManagerInstallExecutionResult:
    operation_id: str
    provider_id: str
    storage_target_id: str
    status: str
    verified: bool
    duration_ms: int
    evidence: dict[str, object]


def _required_text(
    value: object,
    *,
    field: str,
) -> str:
    rendered = (
        ""
        if value is None
        else str(value).strip()
    )

    if not rendered:
        raise ValueError(
            f"{field} is required"
        )

    return rendered


def _validate_request(
    request: BlockchainManagerInstallExecutionRequest,
) -> BlockchainManagerInstallExecutionRequest:
    if not isinstance(
        request,
        BlockchainManagerInstallExecutionRequest,
    ):
        raise ValueError(
            "Invalid Blockchain Manager "
            "install execution request"
        )

    target_asset_id = _required_text(
        request.target_asset_id,
        field="target_asset_id",
    )

    provider_id = _required_text(
        request.provider_id,
        field="provider_id",
    )

    storage_target_id = _required_text(
        request.storage_target_id,
        field="storage_target_id",
    )

    storage_source = _required_text(
        request.storage_source,
        field="storage_source",
    )

    storage_filesystem = _required_text(
        request.storage_filesystem,
        field="storage_filesystem",
    )

    if not _PROVIDER_RE.fullmatch(
        provider_id
    ):
        raise ValueError(
            "provider_id is invalid"
        )

    if not _STORAGE_RE.fullmatch(
        storage_target_id
    ):
        raise ValueError(
            "storage_target_id is invalid"
        )

    return (
        BlockchainManagerInstallExecutionRequest(
            target_asset_id=target_asset_id,
            provider_id=provider_id,
            storage_target_id=storage_target_id,
            storage_source=storage_source,
            storage_filesystem=storage_filesystem,
        )
    )


class BlockchainManagerInstallExecutionService:
    def __init__(
        self,
        *,
        context_service: (
            BlockchainManagerControlContextService
            | None
        ) = None,
        transport_factory: Callable[..., object] = (
            BlockchainManagerControlTransport
        ),
    ) -> None:
        self._context_service = (
            context_service
            or BlockchainManagerControlContextService()
        )

        self._transport_factory = (
            transport_factory
        )

    def execute(
        self,
        request: BlockchainManagerInstallExecutionRequest,
    ) -> BlockchainManagerInstallExecutionResult:
        request = _validate_request(
            request
        )

        context = (
            self._context_service.resolve(
                target_asset_id=(
                    request.target_asset_id
                ),
            )
        )

        if not isinstance(
            context,
            BlockchainManagerControlContext,
        ):
            raise ValueError(
                "Blockchain Manager control "
                "context is invalid"
            )

        if (
            context.target_asset_id
            != request.target_asset_id
        ):
            raise ValueError(
                "Blockchain Manager control "
                "context target mismatch"
            )

        transport = self._transport_factory()

        method = getattr(
            transport,
            "install",
            None,
        )

        if not callable(method):
            raise ValueError(
                "Blockchain Manager control "
                "transport does not support install"
            )

        result = method(
            endpoint=context.endpoint,
            token=context.token,
            ssl_context=context.ssl_context,
            request=BlockchainManagerInstallRequest(
                provider_id=(
                    request.provider_id
                ),
                storage_target_id=(
                    request.storage_target_id
                ),
                storage_source=(
                    request.storage_source
                ),
                storage_filesystem=(
                    request.storage_filesystem
                ),
            ),
        )

        if not isinstance(
            result,
            BlockchainManagerInstallResult,
        ):
            raise ValueError(
                "Blockchain Manager install "
                "transport returned invalid result"
            )

        if (
            result.provider_id
            != request.provider_id
        ):
            raise ValueError(
                "Blockchain Manager install "
                "provider identity mismatch"
            )

        if (
            result.storage_target_id
            != request.storage_target_id
        ):
            raise ValueError(
                "Blockchain Manager install "
                "storage target identity mismatch"
            )

        if (
            result.status
            != "succeeded"
        ):
            raise ValueError(
                "Blockchain Manager install "
                "did not succeed"
            )

        if result.verified is not True:
            raise ValueError(
                "Blockchain Manager install "
                "was not verified"
            )

        operation_id = _required_text(
            result.operation_id,
            field="operation_id",
        )

        evidence = {
            **safe_context_evidence(
                context
            ),
            "providerId":
                result.provider_id,
            "storageTargetId":
                result.storage_target_id,
            "managerOperationId":
                operation_id,
            "status":
                result.status,
            "verified":
                True,
            "durationMs":
                int(result.duration_ms),
        }

        return BlockchainManagerInstallExecutionResult(
            operation_id=operation_id,
            provider_id=result.provider_id,
            storage_target_id=(
                result.storage_target_id
            ),
            status=result.status,
            verified=True,
            duration_ms=int(
                result.duration_ms
            ),
            evidence=evidence,
        )
