from pathlib import Path

repo=Path(__file__).resolve().parents[1]
server=(repo/"backend/api/server.py").read_text()
registration=(repo/"backend/db/repositories/seymour_registration_repository.py").read_text()

assert "seymour_telemetry_routes.handle_get(self)" in server
assert "seymour_telemetry_routes.handle_post(self)" in server
assert "seymour_telemetry_repository.project_document" in registration
assert '"metricsWritten":metrics_written' in registration

print("SBP-018 telemetry integration contract verification: PASS")
