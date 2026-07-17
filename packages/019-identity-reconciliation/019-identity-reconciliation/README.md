# Package 019 — Identity Reconciliation

Reconciles workers by `(source_system, source_worker_id)` while preserving the first persisted `worker_id` as the canonical Nexus ID.

```bash
chmod +x scripts/*.sh
./scripts/doctor.sh
./scripts/install.sh
./scripts/verify.sh
```
