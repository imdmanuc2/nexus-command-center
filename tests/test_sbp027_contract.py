from pathlib import Path

repo = Path(__file__).resolve().parents[1]

registration = (
    repo
    / "backend"
    / "db"
    / "repositories"
    / "seymour_registration_repository.py"
).read_text()

projection = (
    repo
    / "backend"
    / "db"
    / "repositories"
    / "seymour_runtime_state_repository.py"
).read_text()

assert "seymour_runtime_state_repository" in registration
assert "project_document(cur, document)" in registration

required = [
    "runtime.state",
    "runtime.rpc.reachable",
    "runtime.rpc.healthy",
    "runtime.initial_block_download",
    "runtime.verification_progress",
    "observed_state",
]

for marker in required:
    assert marker in projection, marker

print("SBP-027 Nexus CMDB runtime-state ingestion contract verification: PASS")
