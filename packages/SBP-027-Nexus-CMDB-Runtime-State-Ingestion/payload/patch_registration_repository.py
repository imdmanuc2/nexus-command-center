from pathlib import Path

path = Path(
    "backend/db/repositories/"
    "seymour_registration_repository.py"
)
text = path.read_text()

import_line = (
    "from backend.db.repositories import "
    "seymour_runtime_state_repository\n"
)

if import_line not in text:
    marker = (
        "from backend.db.repositories import "
        "seymour_telemetry_repository\n"
    )

    if marker not in text:
        # Some repository revisions use a direct import.
        marker = "import seymour_telemetry_repository\n"
        if marker in text:
            import_line = "import seymour_runtime_state_repository\n"
        else:
            raise SystemExit(
                "Could not locate Seymour telemetry repository import."
            )

    text = text.replace(
        marker,
        marker + import_line,
        1,
    )

call = (
    "seymour_runtime_state_repository."
    "project_document(cur, document)"
)

if call not in text:
    marker = (
        "seymour_telemetry_repository."
        "project_document(cur, document)"
    )

    if marker not in text:
        raise SystemExit(
            "Could not locate Seymour telemetry projection call."
        )

    # Patch every telemetry projection call so both new and duplicate
    # registrations reconcile runtime state.
    text = text.replace(
        marker,
        marker + "\n                "
        + call,
    )

path.write_text(text)
print("Seymour runtime-state registration ingestion wired.")
