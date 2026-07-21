# Package 035 — Remote Deployment & Software Management

Adds the control-plane foundation for safe, auditable remote software and configuration deployments. This package deliberately does **not** execute arbitrary shell commands. It stores catalog entries, deployment intent, target state, approvals, transitions, results, and immutable audit events. Execution adapters can consume approved jobs through the existing allow-listed managed transport and playbook systems.

## Endpoints

- `GET /api/platform/deployments/packages`
- `GET /api/platform/deployments/jobs`
- `GET /api/platform/deployments/job?jobId=...`
- `POST /api/platform/deployments/register-package`
- `POST /api/platform/deployments/create`
- `POST /api/platform/deployments/transition`
- `/deployments.html`

## Workflow

`queued → approved → running → succeeded|failed|partial`, with cancellation supported. Execution transitions require approval context.

## Install

Run `scripts/doctor.sh`, `scripts/install.sh`, and `scripts/verify.sh`.
