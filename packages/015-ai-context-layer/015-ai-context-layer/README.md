# Package 015 — AI Context Layer

Builds derived PostgreSQL context snapshots from assets, workers, pools,
workloads, blockchain nodes, MiningCore, telemetry, events, and alerts.

## Install

```bash
chmod +x scripts/*.sh scripts/*.py
./scripts/doctor.sh
./scripts/install.sh
./scripts/verify.sh
```

## APIs

```text
GET /api/platform/context
GET /api/platform/context/home
GET /api/platform/context/mining
GET /api/platform/context/infrastructure
GET /api/platform/context/health
```

## Commit

```bash
git add   backend/db/migrations/009_ai_context_layer.sql   backend/db/repositories/context_repository.py   backend/services/platform_context_service.py   backend/modules/platform_context.py   backend/jobs/platform_context_job.py   backend/jobs/platform_sync_job.py   backend/api/server.py

git commit -m "Add Platform AI context layer"
git push origin feature/discovery-engine-v2
```
