#!/usr/bin/env python3
from pathlib import Path

path = Path("scripts/sync_platform_inventory.py")
text = path.read_text(encoding="utf-8")

old = """        upsert_worker(worker)
        worker_count += 1

        workload_id = f"workload-{canonical_worker_id}-crypto-mining"
"""

new = """        saved_worker = upsert_worker(worker)
        canonical_worker_id = saved_worker["workerId"]
        worker_count += 1

        workload_id = f"workload-{canonical_worker_id}-crypto-mining"
"""

if old not in text:
    raise SystemExit(
        "Expected worker upsert block was not found. "
        "Run: sed -n '225,245p' scripts/sync_platform_inventory.py"
    )

text = text.replace(old, new, 1)

path.write_text(text, encoding="utf-8")
print("Inventory sync now propagates the repository canonical worker ID.")
