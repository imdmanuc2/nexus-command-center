# Package 016 — Recommendation Engine

Creates prioritized operator recommendations from persisted workers, pools,
blockchain nodes, MiningCore instances, alerts, and Platform context.

## Install

```bash
chmod +x scripts/*.sh scripts/*.py
./scripts/doctor.sh
./scripts/install.sh
./scripts/verify.sh
```

## APIs

```text
GET /api/platform/recommendations
GET /api/platform/recommendations/high-priority
GET /api/platform/recommendations/summary
```

## Commit

```bash
git add   backend/db/migrations/010_recommendation_engine.sql   backend/db/repositories/recommendation_repository.py   backend/services/recommendation_rules   backend/services/recommendation_engine_service.py   backend/modules/platform_recommendations.py   backend/jobs/platform_recommendation_job.py   backend/jobs/platform_sync_job.py   backend/api/server.py

git commit -m "Add Platform recommendation engine"
git push origin feature/discovery-engine-v2
```
