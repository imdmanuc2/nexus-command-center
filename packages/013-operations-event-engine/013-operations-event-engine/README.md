# Package 013 — Operations Event Engine

Tracks state changes for workers, pools, blockchain nodes, and MiningCore
instances and stores durable events in PostgreSQL.

Install:

```bash
chmod +x scripts/*.sh scripts/*.py
./scripts/doctor.sh
./scripts/install.sh
./scripts/verify.sh
```

Commit:

```bash
git add   backend/db/migrations/007_operations_event_engine.sql   backend/db/repositories/platform_event_repository.py   backend/services/platform_event_service.py   backend/modules/platform_events.py   backend/jobs/platform_event_job.py   backend/jobs/platform_sync_job.py   backend/api/server.py

git commit -m "Add Platform operations event engine"
git push origin feature/discovery-engine-v2
```
