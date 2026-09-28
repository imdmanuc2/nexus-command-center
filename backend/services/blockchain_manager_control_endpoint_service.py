"""Resolve the non-secret Blockchain Manager control endpoint for a CMDB target."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import re
from typing import Any, Callable
from urllib.parse import urlunsplit

from backend.db.repositories import service_endpoint_repository
from backend.services import cmdb_service


SERVICE_TYPE = "blockchain-manager-control"
SUBJECT_TYPE = "asset"

_HOSTNAME_RE = re.compile(
    r"^[A-Za-z0-9]"
    r"(?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?$"
)


@dataclass(frozen=True, slots=True)
class BlockchainManagerControlEndpoint:
    target_asset_id: str
    endpoint_id: str
    base_url: str
    protocol: str
    host: str
    port: int
    tls_enabled: bool


def _text(value: Any) -> str:
    return (
        ""
        if value is None
        else str(value).strip()
    )


def _target_asset_id(value: Any) -> str:
    target = _text(
        value
    )

    if not target:
        raise ValueError(
            "target_asset_id is required"
        )

    return target


def _host(value: Any) -> str:
    host = _text(
        value
    )

    if not host:
        raise ValueError(
            "Blockchain Manager endpoint host is missing"
        )

    candidate = host

    if (
        candidate.startswith("[")
        and candidate.endswith("]")
    ):
        candidate = candidate[1:-1]

    try:
        ipaddress.ip_address(
            candidate.split("%", 1)[0]
        )
        return candidate
    except ValueError:
        pass

    if not _HOSTNAME_RE.fullmatch(
        candidate
    ):
        raise ValueError(
            "Blockchain Manager endpoint host is invalid"
        )

    return candidate


def _port(value: Any) -> int:
    try:
        port = int(value)
    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError(
            "Blockchain Manager endpoint port is invalid"
        ) from exc

    if not (
        1 <= port <= 65535
    ):
        raise ValueError(
            "Blockchain Manager endpoint port is invalid"
        )

    return port


def _base_url(
    *,
    protocol: str,
    host: str,
    port: int,
) -> str:
    scheme = protocol.lower()

    if scheme not in {
        "http",
        "https",
    }:
        raise ValueError(
            "Blockchain Manager endpoint "
            "must use HTTP or HTTPS"
        )

    rendered_host = host

    try:
        parsed = ipaddress.ip_address(
            host.split("%", 1)[0]
        )

        if parsed.version == 6:
            rendered_host = (
                "[" + host + "]"
            )
    except ValueError:
        pass

    return urlunsplit(
        (
            scheme,
            f"{rendered_host}:{port}",
            "",
            "",
            "",
        )
    )


class BlockchainManagerControlEndpointService:
    def __init__(
        self,
        *,
        asset_loader: Callable[
            [str],
            dict[str, Any] | None,
        ] = cmdb_service.get_asset,
        endpoint_loader: Callable[..., list[
            dict[str, Any]
        ]] = service_endpoint_repository.find_for_subject,
    ) -> None:
        self._asset_loader = (
            asset_loader
        )

        self._endpoint_loader = (
            endpoint_loader
        )

    def resolve(
        self,
        *,
        target_asset_id: str,
    ) -> BlockchainManagerControlEndpoint:
        target_id = _target_asset_id(
            target_asset_id
        )

        response = self._asset_loader(
            target_id
        )

        if not isinstance(
            response,
            dict,
        ):
            raise ValueError(
                "CMDB returned invalid Blockchain Manager "
                "control target response"
            )

        if _text(
            response.get("status")
        ).lower() != "ok":
            raise ValueError(
                "Blockchain Manager control target "
                "does not exist in CMDB"
            )

        asset = response.get(
            "asset"
        )

        if not isinstance(
            asset,
            dict,
        ):
            raise ValueError(
                "CMDB returned invalid Blockchain Manager "
                "control target asset"
            )

        canonical_id = _text(
            asset.get("id")
        )

        if canonical_id != target_id:
            raise ValueError(
                "Target CMDB asset identity mismatch"
            )

        if not bool(
            asset.get("managed")
        ):
            raise ValueError(
                "Blockchain Manager control "
                "requires a managed CMDB asset"
            )

        platform_id = _text(
            asset.get(
                "deploymentPlatformId"
            )
        )

        if platform_id != "umbrel":
            raise ValueError(
                "Blockchain Manager control "
                "requires Umbrel deployment platform"
            )

        rows = self._endpoint_loader(
            subject_type=SUBJECT_TYPE,
            subject_id=target_id,
            service_type=SERVICE_TYPE,
        )

        if len(rows) != 1:
            raise ValueError(
                "Exactly one Blockchain Manager "
                "control endpoint is required"
            )

        row = rows[0]

        if not isinstance(
            row,
            dict,
        ):
            raise ValueError(
                "Blockchain Manager endpoint is invalid"
            )

        if _text(
            row.get("subject_type")
        ) != SUBJECT_TYPE:
            raise ValueError(
                "Blockchain Manager endpoint "
                "subject type mismatch"
            )

        if _text(
            row.get("subject_id")
        ) != target_id:
            raise ValueError(
                "Blockchain Manager endpoint "
                "target identity mismatch"
            )

        if _text(
            row.get("service_type")
        ) != SERVICE_TYPE:
            raise ValueError(
                "Blockchain Manager endpoint "
                "service type mismatch"
            )

        endpoint_id = _text(
            row.get("endpoint_id")
        )

        if not endpoint_id:
            raise ValueError(
                "Blockchain Manager endpoint id is missing"
            )

        protocol = _text(
            row.get("protocol")
        ).lower()

        tls_enabled = bool(
            row.get("tls_enabled")
        )

        if (
            protocol != "https"
            or tls_enabled is not True
        ):
            raise ValueError(
                "Blockchain Manager control "
                "requires authenticated HTTPS"
            )

        host = _host(
            row.get("host")
        )

        port = _port(
            row.get("port")
        )

        path = _text(
            row.get("path")
        )

        if path not in {
            "",
            "/",
        }:
            raise ValueError(
                "Blockchain Manager control endpoint "
                "must be registered at service root"
            )

        status = _text(
            row.get("status")
        ).lower()

        if status in {
            "disabled",
            "retired",
        }:
            raise ValueError(
                "Blockchain Manager control "
                "endpoint is not active"
            )

        return BlockchainManagerControlEndpoint(
            target_asset_id=target_id,
            endpoint_id=endpoint_id,
            base_url=_base_url(
                protocol=protocol,
                host=host,
                port=port,
            ),
            protocol=protocol,
            host=host,
            port=port,
            tls_enabled=tls_enabled,
        )
