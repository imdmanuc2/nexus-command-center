from pathlib import Path
repo = Path(__file__).resolve().parents[1]
text = (repo / "scripts/acceptance/verify_sbp028_live_runtime_state.py").read_text()
assert '"runtime.state"' not in text
assert '"runtime.rpc.reachable"' in text
assert '"runtime.rpc.healthy"' in text
assert '"runtime.initial_block_download"' in text
assert '"runtime.verification_progress"' in text
assert '"runtimeState"' in text
print("SBP-027.2 acceptance contract verification: PASS")
