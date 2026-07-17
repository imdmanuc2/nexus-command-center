# Package 004 — PostgreSQL Asset Writes

This package changes the existing asset manager's persistence functions to use
PostgreSQL while preserving normalization, classification, reconciliation, and
existing API contracts.

## Install

```bash
cd ~/Projects/Seymour/nexus-command-center
chmod +x packages/004-postgresql-asset-writes/scripts/*.sh
packages/004-postgresql-asset-writes/scripts/install.sh
sudo systemctl restart nexus-api.service
packages/004-postgresql-asset-writes/scripts/verify.sh
```

The verification updates and restores one asset note, confirms the value is
read from PostgreSQL, and proves `backend/data/assets.json` was not modified.

## Commit

```bash
git add \
  backend/core/asset_manager.py \
  backend/db/repositories/asset_repository_extensions.py

git commit -m "Move CMDB asset writes to PostgreSQL"
git push origin feature/discovery-engine-v2
```
