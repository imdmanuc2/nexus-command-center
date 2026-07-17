# Package 014 — Alert Engine

Turns durable Platform events into deduplicated operational alerts.

Install:

```bash
chmod +x scripts/*.sh scripts/*.py
./scripts/doctor.sh
./scripts/install.sh
./scripts/verify.sh
```

Initial rules:

- resource offline
- resource degraded
- endpoint changed
- version changed

APIs:

```text
GET /api/platform/alerts
GET /api/platform/alerts/active
GET /api/platform/alerts/summary
```

Commit:

```bash
git add   backend/db/migrations/008_alert_engine.sql   backend/db/repositories/alert_repository.py   backend/services/alert_engine_service.py   backend/modules/platform_alerts.py   backend/jobs/platform_alert_job.py   backend/jobs/platform_sync_job.py   backend/api/server.py

git commit -m "Add Platform alert engine"
git push origin feature/discovery-engine-v2
```
