# Package 047 — Change Rollback Orchestration & Recovery
Adds durable rollback plans, approval, execution, verification, stale lease recovery, manual-intervention state, history, audit events, and a dedicated rollback worker.

## APIs
- `GET /api/change-rollbacks/status`
- `GET /api/change-rollbacks/history`
- `POST /api/change-rollbacks`
- `POST /api/change-rollbacks/approve`
- `POST /api/change-rollbacks/queue`
