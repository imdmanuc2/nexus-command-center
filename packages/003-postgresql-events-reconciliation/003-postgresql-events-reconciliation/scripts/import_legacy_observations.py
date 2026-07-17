#!/usr/bin/env python3
import json
from pathlib import Path
from backend.db.repositories.observation_repository import append_observation
p=Path("backend/data/cmdb/observations/observations.jsonl")
if not p.exists(): print("No legacy observations JSONL found."); raise SystemExit(0)
n=0
for line in p.read_text(encoding="utf-8").splitlines():
    try: append_observation(json.loads(line)); n+=1
    except json.JSONDecodeError: pass
print(f"Imported {n} legacy observations.")
