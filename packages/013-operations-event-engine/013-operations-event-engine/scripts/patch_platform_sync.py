#!/usr/bin/env python3
from pathlib import Path

path = Path("backend/jobs/platform_sync_job.py")
text = path.read_text(encoding="utf-8")

import_block = """from backend.services.platform_event_service import (
    evaluate_platform_state,
)
"""

if import_block not in text:
    anchor = """from backend.jobs.platform_resource_sync import (
    synchronize_platform_resources,
)
"""
    if anchor not in text:
        raise SystemExit("Could not find resource sync import anchor.")

    text = text.replace(
        anchor,
        anchor + import_block,
        1,
    )

if "events = evaluate_platform_state()" not in text:
    anchor = """    stale = reconcile_stale_state(
        stale_seconds=stale_seconds,
        dry_run=dry_run,
    )
"""

    if anchor not in text:
        raise SystemExit(
            "Could not find stale reconciliation block."
        )

    replacement = (
        anchor
        + "\n"
        + "    events = evaluate_platform_state()\n"
    )

    text = text.replace(
        anchor,
        replacement,
        1,
    )

if '"eventEngine": events' not in text:
    anchor = '        "resourcePersistence": resources,\n'

    if anchor not in text:
        raise SystemExit(
            "Could not find result payload anchor."
        )

    text = text.replace(
        anchor,
        anchor + '        "eventEngine": events,\n',
        1,
    )

path.write_text(text, encoding="utf-8")
print("Integrated Platform event engine into one-minute sync.")
