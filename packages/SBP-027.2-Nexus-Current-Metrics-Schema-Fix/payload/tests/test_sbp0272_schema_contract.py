from pathlib import Path
repo = Path(__file__).resolve().parents[1]
text = (repo / "backend/db/repositories/seymour_runtime_state_repository.py").read_text()
for marker in [
    "subject_type",
    "dimensions",
    "data",
    "'blockchain-node'",
    "runtime.rpc.reachable",
    "runtime.rpc.healthy",
    "runtime.initial_block_download",
    "runtime.verification_progress",
    "observed_patch = {",
    '"runtimeState": state',
]:
    assert marker in text, marker
assert '"runtime.state"' not in text
print("SBP-027.2 current_metrics schema contract verification: PASS")
