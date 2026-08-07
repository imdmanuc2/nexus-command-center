# Package 047 — Change Rollback Orchestration & Recovery
Adds durable rollback plans, approval, execution, verification, stale lease recovery, manual-intervention state, history, audit events, and a dedicated rollback worker.

## APIs
- `GET /api/change-rollbacks/status`
- `GET /api/change-rollbacks/history`
- `POST /api/change-rollbacks`
- `POST /api/change-rollbacks/approve`
- `POST /api/change-rollbacks/queue`


## Revision 2

Uses an AST-aware `server.py` installer rather than package-specific string
anchors. Routes are inserted before each handler's fallback statement, Python
syntax is validated, and the saved file is re-read before success is reported.
