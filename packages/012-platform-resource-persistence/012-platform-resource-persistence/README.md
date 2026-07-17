# Package 012 — Platform Resource Persistence

Completes MiningCore persistence against the mature Nexus PostgreSQL schema.

```bash
chmod +x scripts/*.sh
./scripts/doctor.sh
./scripts/install.sh
./scripts/verify.sh
```

Expected counts:

```text
blockchain_nodes       1
miningcore_instances   2
```

Commit:

```bash
git add backend/db/repositories/blockchain_repository.py backend/services/blockchain_sync_service.py backend/db/repositories/miningcore_repository.py backend/services/miningcore_sync_service.py backend/jobs/platform_resource_sync.py backend/jobs/platform_sync_job.py backend/modules/platform_nodes.py backend/modules/platform_miningcore.py backend/api/server.py backend/db/migrations/006_platform_resource_persistence.sql
git commit -m "Complete Platform resource persistence"
git push origin feature/discovery-engine-v2
```
