from pathlib import Path

path = Path("backend/api/server.py")
text = path.read_text()

registration_import = "from backend.api import seymour_registration_routes\n"
telemetry_import = "from backend.api import seymour_telemetry_routes\n"

if telemetry_import not in text:
    if registration_import not in text:
        raise SystemExit("Could not locate Seymour registration import.")
    text = text.replace(registration_import, registration_import + telemetry_import, 1)

for handler in ("handle_get", "handle_post"):
    marker = f"seymour_telemetry_routes.{handler}(self)"
    if marker in text:
        continue
    registration_block = (
        f"        if seymour_registration_routes.{handler}(self):\n"
        "            return\n\n"
    )
    if registration_block not in text:
        raise SystemExit(f"Could not locate registration {handler} block.")
    telemetry_block = (
        registration_block
        + f"        if seymour_telemetry_routes.{handler}(self):\n"
        + "            return\n\n"
    )
    text = text.replace(registration_block, telemetry_block, 1)

path.write_text(text)
print("Seymour telemetry API routes installed.")
