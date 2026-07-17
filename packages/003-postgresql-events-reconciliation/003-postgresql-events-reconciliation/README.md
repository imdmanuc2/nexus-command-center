# Package 003 — PostgreSQL Audit, Observations, and Reconciliation

Install:

```bash
chmod +x packages/003-postgresql-events-reconciliation/scripts/*.sh
packages/003-postgresql-events-reconciliation/scripts/install.sh
sudo systemctl restart nexus-api.service
packages/003-postgresql-events-reconciliation/scripts/verify.sh
```

This switches the existing audit and observation compatibility functions from
JSONL to PostgreSQL and imports the legacy JSONL records. It also adds the
PostgreSQL reconciliation-case repository.

After verification:

```bash
git add backend/db/repositories backend/core/cmdb_audit.py \
  backend/core/observation_engine.py \
  scripts/import_legacy_audit.py scripts/import_legacy_observations.py
git commit -m "Move CMDB audit and observations to PostgreSQL"
git push origin feature/discovery-engine-v2
```

Do not commit `*.before-postgresql-*` or runtime JSONL files.
