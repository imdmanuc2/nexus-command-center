from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from backend.executors.blockchain_deployment_executor import (
    DeploymentRequest,
    DeploymentStepOutput,
)
from backend.services import cmdb_service
from backend.services.blockchain_target_platform import (
    TargetPlatformProfile,
    resolve_target_platform_profile,
)
from backend.transports.models import TransportTarget
from backend.transports.target_resolver import resolve_target


@dataclass(frozen=True, slots=True)
class DeploymentTargetContext:
    target: TransportTarget
    profile: TargetPlatformProfile


class BlockchainDeploymentTargetService:
    """
    Resolve a blockchain deployment target using CMDB as the
    infrastructure and deployment-platform authority.

    Public deployment requests select only a canonical CMDB asset ID.
    SSH connection/trust material and platform profile remain private
    to Nexus.

    deploymentPlatformId must be explicitly stored in CMDB. The
    platform is never inferred from hostname, username, IP address,
    operating system, capabilities, or filesystem layout.
    """

    def __init__(
        self,
        *,
        asset_getter: Callable[[str], dict[str, Any]] | None = None,
        target_resolver: Callable[
            [dict[str, Any]], TransportTarget
        ] | None = None,
        platform_resolver: Callable[
            [str], TargetPlatformProfile
        ] | None = None,
    ) -> None:
        self._asset_getter = asset_getter or cmdb_service.get_asset
        self._target_resolver = target_resolver or resolve_target
        self._platform_resolver = (
            platform_resolver
            or resolve_target_platform_profile
        )

    def resolve(
        self,
        request: DeploymentRequest,
    ) -> DeploymentStepOutput:
        asset_id = str(
            request.target_asset_id or ""
        ).strip()

        if not asset_id:
            raise ValueError(
                "Blockchain deployment target asset ID is required"
            )

        response = self._asset_getter(
            asset_id
        )

        if not isinstance(response, dict):
            raise ValueError(
                "CMDB returned invalid deployment target response"
            )

        if response.get("status") != "ok":
            raise ValueError(
                "Blockchain deployment target does not exist in CMDB"
            )

        asset = response.get("asset")

        if not isinstance(asset, dict):
            raise ValueError(
                "CMDB returned invalid deployment target asset"
            )

        canonical_id = str(
            asset.get("id") or ""
        ).strip()

        if canonical_id != asset_id:
            raise ValueError(
                "CMDB deployment target identity mismatch"
            )

        if not bool(asset.get("managed")):
            raise ValueError(
                "Blockchain deployment target is not Nexus-managed"
            )

        deployment_platform_id = str(
            asset.get("deploymentPlatformId")
            or ""
        ).strip()

        if not deployment_platform_id:
            raise ValueError(
                "Blockchain deployment target has no explicit "
                "deployment platform classification"
            )

        profile = self._platform_resolver(
            deployment_platform_id
        )

        if not isinstance(
            profile,
            TargetPlatformProfile,
        ):
            raise ValueError(
                "Deployment platform resolver returned invalid profile"
            )

        if profile.platform_id != deployment_platform_id:
            raise ValueError(
                "Deployment platform profile identity mismatch"
            )

        target = self._target_resolver({
            "entityId": canonical_id,
            "inputPayload": {
                "assetId": canonical_id,
                "transport": "ssh",
            },
        })

        if not isinstance(
            target,
            TransportTarget,
        ):
            raise ValueError(
                "Managed-host resolver returned invalid target"
            )

        if target.asset_id != canonical_id:
            raise ValueError(
                "Resolved transport target identity mismatch"
            )

        if target.transport != "ssh":
            raise ValueError(
                "Blockchain deployment requires SSH transport"
            )

        if not str(
            target.host or ""
        ).strip():
            raise ValueError(
                "Blockchain deployment SSH host is missing"
            )

        if not str(
            target.username or ""
        ).strip():
            raise ValueError(
                "Blockchain deployment SSH username is missing"
            )

        if not str(
            target.known_hosts_file or ""
        ).strip():
            raise ValueError(
                "Blockchain deployment known-hosts file is missing"
            )

        context = DeploymentTargetContext(
            target=target,
            profile=profile,
        )

        return DeploymentStepOutput(
            evidence={
                "targetAssetId": canonical_id,
                "transport": "ssh",
                "deploymentPlatformId": (
                    profile.platform_id
                ),
            },
            private=context,
        )
