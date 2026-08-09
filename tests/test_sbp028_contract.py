from pathlib import Path

repo = Path(__file__).resolve().parents[1]

projection = (
    repo
    / "backend"
    / "db"
    / "repositories"
    / "seymour_runtime_state_repository.py"
).read_text()

registration = (
    repo
    / "backend"
    / "db"
    / "repositories"
    / "seymour_registration_repository.py"
).read_text()

required = [
    "runtime.state",
    "runtime.rpc.reachable",
    "runtime.rpc.healthy",
    "runtime.initial_block_download",
    "runtime.verification_progress",
]

for marker in required:
    assert marker in projection, marker

assert "seymour_runtime_state_repository" in registration
assert "project_document(cur, document)" in registration

print("SBP-028 live acceptance contract verification: PASS")
