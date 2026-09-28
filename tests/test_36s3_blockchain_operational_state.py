import unittest

from backend.services.operational_state_engine import (
    derive_blockchain_operational_state,
)


class BlockchainOperationalStateTests(unittest.TestCase):

    def test_persisted_rpc_connected_and_synced_is_healthy(self):
        asset = {}
        node = {
            "rpcConnected": True,
            "syncPercent": 100.0,
        }

        self.assertEqual(
            derive_blockchain_operational_state(asset, node),
            {
                "observedOperationalState": "synchronized",
                "health": "healthy",
                "connectivity": "connected",
            },
        )

    def test_persisted_rpc_connected_while_syncing_is_warning(self):
        asset = {}
        node = {
            "rpcConnected": True,
            "syncPercent": 42.0,
        }

        self.assertEqual(
            derive_blockchain_operational_state(asset, node),
            {
                "observedOperationalState": "synchronizing",
                "health": "warning",
                "connectivity": "connected",
            },
        )

    def test_current_runtime_rpc_overrides_stale_offline_projection(self):
        asset = {
            "observedState": {
                "telemetry": {
                    "runtimeState": "syncing",
                    "runtimeRpcHealthy": True,
                    "runtimeRpcReachable": True,
                    "operationalState": {
                        "state": "syncing",
                        "running": True,
                        "installed": True,
                        "rpcHealthy": True,
                        "rpcReachable": True,
                        "containerHealth": "healthy",
                        "initialBlockDownload": True,
                    },
                    "container": {
                        "found": True,
                        "health": "healthy",
                        "status": "running",
                        "running": True,
                        "available": True,
                    },
                },
            },
        }

        node = {
            "rpcConnected": False,
            "status": "offline",
            "syncPercent": None,
        }

        self.assertEqual(
            derive_blockchain_operational_state(asset, node),
            {
                "observedOperationalState": "synchronizing",
                "health": "warning",
                "connectivity": "connected",
            },
        )

    def test_running_without_positive_rpc_evidence_remains_fail_closed(self):
        asset = {
            "observedState": {
                "telemetry": {
                    "runtimeState": "syncing",
                    "runtimeRpcHealthy": False,
                    "runtimeRpcReachable": False,
                    "operationalState": {
                        "state": "syncing",
                        "running": True,
                        "rpcHealthy": False,
                        "rpcReachable": False,
                    },
                    "container": {
                        "running": True,
                        "health": "healthy",
                    },
                },
            },
        }

        node = {
            "rpcConnected": False,
            "syncPercent": None,
        }

        self.assertEqual(
            derive_blockchain_operational_state(asset, node),
            {
                "observedOperationalState": "offline",
                "health": "critical",
                "connectivity": "disconnected",
            },
        )

    def test_no_runtime_evidence_preserves_existing_fail_closed_behavior(self):
        asset = {}
        node = {
            "rpcConnected": False,
            "syncPercent": None,
        }

        self.assertEqual(
            derive_blockchain_operational_state(asset, node),
            {
                "observedOperationalState": "offline",
                "health": "critical",
                "connectivity": "disconnected",
            },
        )


if __name__ == "__main__":
    unittest.main()
