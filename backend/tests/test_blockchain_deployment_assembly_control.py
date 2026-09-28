from __future__ import annotations

from backend.services.blockchain_deployment_storage_service import DeploymentStorageContext

import unittest
from unittest.mock import MagicMock, patch

from backend.executors.blockchain_deployment_executor import (
    BlockchainDeploymentExecutor,
    DeploymentRequest,
)
from backend.services.blockchain_deployment_assembly_service import (
    BlockchainDeploymentAssemblyService,
)
from backend.services.blockchain_deployment_preflight_service import (
    BlockchainDeploymentPreflightContext,
    BlockchainDeploymentPreflightResult,
)
from backend.services.blockchain_target_platform import (
    UMBREL_TARGET_PROFILE,
)
from backend.transports.models import TransportTarget
from backend.transports.target_prerequisites import (
    TargetPrerequisiteResult,
)


class BlockchainDeploymentAssemblyControlTests(
    unittest.TestCase
):
    def _request(self):
        return DeploymentRequest(
            provider_id="bitcoin-mainnet",
            storage_target_id="storage-main",
            target_asset_id="asset-managed-1",
            correlation_id="corr-control",
            approved_by="operator",
        )

    def _preflight(self):
        target = TransportTarget(
            asset_id="asset-managed-1",
            transport="ssh",
            host="192.0.2.10",
            username="umbrel",
            known_hosts_file="/private/known_hosts",
        )

        prerequisites = TargetPrerequisiteResult(
            platform_id="umbrel",
            python_version="Python 3.11.9",
            tar_version="tar (GNU tar) 1.34",
            checks=("python3-executable",),
            duration_ms=1,
            host_key_verified=True,
        )

        return BlockchainDeploymentPreflightResult(
            context=BlockchainDeploymentPreflightContext(
                target=target,
                profile=UMBREL_TARGET_PROFILE,
                storage=DeploymentStorageContext(
                    storage_asset_id="storage-main",
                    storage_asset_type="storage",
                    target_asset_id=(target).asset_id,
                    storage_source="/dev/sda6",
                    storage_filesystem="ext4",
                    storage_mount_path="/private/not-public",
                ),
                prerequisites=prerequisites,
            ),
            evidence={
                "targetAssetId": "asset-managed-1",
                "transport": "ssh",
                "deploymentPlatformId": "umbrel",
            },
        )

    def test_control_is_passed_to_executor(self):
        control = MagicMock()

        assembler = BlockchainDeploymentAssemblyService(
            artifact_transport_factory=MagicMock(
                return_value=MagicMock()
            ),
            bootstrap_transport_factory=MagicMock(
                return_value=MagicMock()
            ),
            runtime_verification_transport_factory=MagicMock(
                return_value=MagicMock()
            ),
            installer_transport_factory=MagicMock(
                return_value=MagicMock()
            ),
            installation_verification_transport_factory=MagicMock(
                return_value=MagicMock()
            ),
        )

        captured = {}

        real_init = BlockchainDeploymentExecutor.__init__

        def capture_init(instance, *args, **kwargs):
            captured.update(kwargs)
            return real_init(instance, *args, **kwargs)

        with patch.object(
            BlockchainDeploymentExecutor,
            "__init__",
            capture_init,
        ):
            executor = assembler.assemble(
                request=self._request(),
                preflight=self._preflight(),
                execution_control=control,
            )

        self.assertIsInstance(
            executor,
            BlockchainDeploymentExecutor,
        )

        self.assertIs(
            captured["execution_control"],
            control,
        )

    def test_control_defaults_to_none(self):
        assembler = BlockchainDeploymentAssemblyService(
            artifact_transport_factory=MagicMock(
                return_value=MagicMock()
            ),
            bootstrap_transport_factory=MagicMock(
                return_value=MagicMock()
            ),
            runtime_verification_transport_factory=MagicMock(
                return_value=MagicMock()
            ),
            installer_transport_factory=MagicMock(
                return_value=MagicMock()
            ),
            installation_verification_transport_factory=MagicMock(
                return_value=MagicMock()
            ),
        )

        captured = {}

        real_init = BlockchainDeploymentExecutor.__init__

        def capture_init(instance, *args, **kwargs):
            captured.update(kwargs)
            return real_init(instance, *args, **kwargs)

        with patch.object(
            BlockchainDeploymentExecutor,
            "__init__",
            capture_init,
        ):
            assembler.assemble(
                request=self._request(),
                preflight=self._preflight(),
            )

        self.assertIsNone(
            captured["execution_control"]
        )


if __name__ == "__main__":
    unittest.main()
