from pathlib import Path
repo = Path(__file__).resolve().parents[1]
text = (repo / "backend/db/repositories/seymour_runtime_state_repository.py").read_text()
for marker in [
    "observed_patch = {",
    '"runtimeState": state',
    '"runtimeStateReason"',
    '"runtimeRpcReachable"',
    '"runtimeRpcHealthy"',
    '"runtimeInitialBlockDownload"',
    '"runtimeVerificationProgress"',
    "COALESCE(",
    "'{}'::jsonb",
]:
    assert marker in text, marker
assert "observed_state = %s" not in text
print("SBP-027.1 observed_state JSONB merge contract verification: PASS")
