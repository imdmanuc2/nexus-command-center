# Package 046 — Change Execution Worker & Reconciliation

Completes the controlled-change execution plane introduced by Package 045.

## Included

- Durable queue worker with PostgreSQL `FOR UPDATE SKIP LOCKED` claims
- Worker leases and stale-operation reconciliation
- Allow-listed capability validation
- Managed local/SSH transport dispatch
- Approval enforcement
- Structured and redacted execution results
- Post-action verification
- Change-step and change-status reconciliation
- Execution attempt history
- Worker status and history APIs
- systemd-managed execution worker

## APIs

- `GET /api/change-execution/status`
- `GET /api/change-execution/history`

The worker never executes arbitrary shell text. It resolves only capabilities
registered in `backend/capabilities/registry.py`.


## Revision 3

- Installs the canonical `nexus.operation_queue` and event schema when absent.
- Keeps the worker idle instead of crashing when queue availability changes.
- Fixes JSON encoding for status endpoint error responses.
- Installs the systemd service with the actual repository owner.
- Adds restart-loop detection to verification.
