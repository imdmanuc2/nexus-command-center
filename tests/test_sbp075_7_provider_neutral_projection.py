from backend.db.repositories.seymour_registration_repository import (
    _operational_status,
    _provider_implementation,
)


def test_bitcoin_provider_uses_bitcoin_core():
    asset = {
        "assetType": "blockchain-node",
        "providerId": "bitcoin-mainnet",
        "coin": "BTC",
        "telemetry": {},
    }
    assert _provider_implementation(asset) == "Bitcoin Core"


def test_bitcoin_cash_provider_uses_bchn():
    asset = {
        "assetType": "blockchain-node",
        "providerId": "bitcoin-cash-mainnet",
        "coin": "BCH",
        "telemetry": {},
    }
    assert _provider_implementation(asset) == "Bitcoin Cash Node"


def test_monero_provider_uses_monero():
    asset = {
        "assetType": "blockchain-node",
        "providerId": "monero-mainnet",
        "coin": "XMR",
        "telemetry": {},
    }
    assert _provider_implementation(asset) == "Monero"


def test_explicit_telemetry_implementation_wins():
    asset = {
        "providerId": "bitcoin-mainnet",
        "coin": "BTC",
        "telemetry": {"implementation": "Custom Bitcoin Runtime"},
    }
    assert _provider_implementation(asset) == "Custom Bitcoin Runtime"


def test_unknown_provider_never_defaults_to_bitcoin_cash():
    asset = {
        "providerId": "future-chain-mainnet",
        "coin": "FUT",
        "telemetry": {},
    }
    implementation = _provider_implementation(asset)
    assert implementation == "FUT Node"
    assert implementation != "Bitcoin Cash Node"


def test_runtime_state_running_projects_running():
    asset = {
        "telemetry": {
            "runtimeState": "running",
            "running": True,
        }
    }
    assert _operational_status(asset) == "running"


def test_running_boolean_projects_running():
    asset = {"telemetry": {"running": True}}
    assert _operational_status(asset) == "running"


def test_running_false_projects_stopped():
    asset = {"telemetry": {"running": False}}
    assert _operational_status(asset) == "stopped"


def test_explicit_offline_projects_stopped():
    asset = {
        "status": "offline",
        "telemetry": {"running": True},
    }
    assert _operational_status(asset) == "stopped"


def test_missing_state_is_unknown():
    assert _operational_status({"telemetry": {}}) == "unknown"
