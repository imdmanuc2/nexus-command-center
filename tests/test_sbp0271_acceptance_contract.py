from pathlib import Path
repo = Path(__file__).resolve().parents[1]
text = (repo / "scripts/acceptance/verify_sbp028_live_runtime_state.py").read_text()
assert 'observed_state.get(' in text
assert '"runtimeState"' in text
assert "observed_state.runtimeState" in text
print("SBP-027.1 SBP-028 acceptance contract verification: PASS")
