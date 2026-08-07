from pathlib import Path

path = Path("backend/db/repositories/seymour_registration_repository.py")
text = path.read_text()

import_line = "from backend.db.repositories import seymour_telemetry_repository\n"
anchor = "from backend.db.connection import transaction\n"

if import_line not in text:
    if anchor not in text:
        raise SystemExit("Could not locate transaction import.")
    text = text.replace(anchor, anchor + import_line, 1)

duplicate_old = (
    '                result=existing["result"] or {}\n'
    '                return {**result,"duplicate":True,"registrationId":registration_id}\n'
)

duplicate_new = (
    '                result=existing["result"] or {}\n'
    '                seymour_telemetry_repository.project_document(cur, document)\n'
    '                cur.execute(\n'
    '                    "UPDATE nexus.seymour_registrations SET last_seen_at=NOW() WHERE registration_id=%s",\n'
    '                    (registration_id,),\n'
    '                )\n'
    '                return {**result,"duplicate":True,"registrationId":registration_id}\n'
)

if "SET last_seen_at=NOW()" not in text:
    if duplicate_old not in text:
        raise SystemExit("Could not locate duplicate registration block.")
    text = text.replace(duplicate_old, duplicate_new, 1)

projection_marker = (
    '            result={\n'
    '                "status":"accepted","registrationId":registration_id,\n'
)

projection_block = (
    '            metrics_written = seymour_telemetry_repository.project_document(cur, document)\n\n'
    '            result={\n'
    '                "status":"accepted","registrationId":registration_id,\n'
)

if "metrics_written = seymour_telemetry_repository.project_document" not in text:
    if projection_marker not in text:
        raise SystemExit("Could not locate result block.")
    text = text.replace(projection_marker, projection_block, 1)

result_marker = (
    '                "relationshipCount":len([x for x in document.get("relationships",[]) if isinstance(x,dict)]),\n'
    '                "duplicate":False,\n'
)

result_replacement = (
    '                "relationshipCount":len([x for x in document.get("relationships",[]) if isinstance(x,dict)]),\n'
    '                "metricsWritten":metrics_written,\n'
    '                "duplicate":False,\n'
)

if '"metricsWritten":metrics_written' not in text:
    if result_marker not in text:
        raise SystemExit("Could not locate result metric insertion.")
    text = text.replace(result_marker, result_replacement, 1)

path.write_text(text)
print("Seymour registration telemetry projection installed.")
