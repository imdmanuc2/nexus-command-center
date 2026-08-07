# SBP-017 — Nexus Registration Receiver & CMDB Ingestion

Target repository: ~/Projects/Seymour/nexus-command-center
Target branch: feature/discovery-engine-v2

Adds authenticated Seymour registration receiving, idempotency, CMDB asset and
blockchain-node reconciliation, relationships, current metrics, and audit
evidence.

API:
- POST /api/integrations/seymour/registration
- GET /api/integrations/seymour/registration/status

The installer does not restart nexus-api.service automatically.
