from backend.db.repositories import (
    seymour_runtime_state_repository as repository,
)


def test_running_is_valid_runtime_state():
    assert "running" in repository.VALID_STATES


def test_runtime_state_contract_is_not_bch_only():
    source = open(
        repository.__file__,
        encoding="utf-8",
    ).read()

    assert (
        'asset.get("providerId") != "bitcoin-cash-mainnet"'
        not in source
    )


def test_asset_runtime_accepts_running_state():
    state, runtime = repository._asset_runtime(
        {
            "runtimeState": "running",
            "telemetry": {},
        }
    )

    assert state == "running"
    assert runtime["state"] == "running"


def test_asset_runtime_preserves_rpc_observation():
    state, runtime = repository._asset_runtime(
        {
            "runtimeState": "running",
            "telemetry": {
                "runtimeRpcReachable": True,
                "runtimeRpcHealthy": True,
            },
        }
    )

    assert state == "running"
    assert runtime["rpcReachable"] is True
    assert runtime["rpcHealthy"] is True


def test_managed_runtime_default_rpc_connected_is_not_authoritative():
    source = open(
        "backend/services/blockchain_operations_service.py",
        encoding="utf-8",
    ).read()

    assert "native_rpc_connected" in source
    assert "if manager is None" in source
    assert '"rpcConnected": native_rpc_connected' in source


def test_managed_runtime_default_node_status_is_not_authoritative():
    source = open(
        "backend/services/blockchain_operations_service.py",
        encoding="utf-8",
    ).read()

    assert "authoritative_node_status" in source
    assert '"nodeStatus": authoritative_node_status' in source
