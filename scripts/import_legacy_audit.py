#!/usr/bin/env python3
import json
from pathlib import Path
from backend.db.repositories.audit_repository import append_event
p=Path("backend/data/cmdb/audit-events.jsonl")
if not p.exists(): print("No legacy audit JSONL found."); raise SystemExit(0)
n=0
for line in p.read_text(encoding="utf-8").splitlines():
    try: append_event(json.loads(line)); n+=1
    except json.JSONDecodeError: pass
print(f"Imported {n} legacy audit events.")
