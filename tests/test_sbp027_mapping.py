from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

repo = Path(__file__).resolve().parents[1]
path = (
    repo
    / "backend"
    / "db"
    / "repositories"
    / "seymour_runtime_state_repository.py"
)

spec = spec_from_file_location(
    "sbp027_runtime_projection",
    path,
)
module = module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

asset = {
    "assetId": "asset-bch-test",
    "providerId": "bitcoin-cash-mainnet",
    "runtimeState": "syncing",
    "telemetry": {
        "runtimeState": "syncing",
        "runtimeStateReason": "Initial block download is active.",
        "runtimeRpcReachable": True,
        "runtimeRpcHealthy": True,
        "runtimeInitialBlockDownload": True,
        "runtimeVerificationProgress": 0.42,
    },
}

state, values = module._asset_runtime(asset)

assert state == "syncing"
assert values["rpcReachable"] is True
assert values["rpcHealthy"] is True
assert values["initialBlockDownload"] is True
assert values["verificationProgress"] == 0.42

print("SBP-027 runtime-state mapping verification: PASS")
