# Nexus CMDB PostgreSQL Milestone 1

This package moves canonical CMDB asset reads to PostgreSQL while keeping the
existing `/api/cmdb/assets`, `/api/cmdb/summary`, and `/api/cmdb/audit`
response contracts.

## Install

```bash
cd ~/Projects/Seymour/nexus-command-center
unzip /path/to/nexus_cmdb_postgres_milestone_1.zip -d /tmp/nexus-cmdb-m1
chmod +x /tmp/nexus-cmdb-m1/scripts/*.sh
/tmp/nexus-cmdb-m1/scripts/install_cmdb_postgres_milestone_1.sh
```

Back up and import:

```bash
cp backend/data/assets.json \
  backend/data/assets.json.before-postgresql-import-$(date +%Y%m%d-%H%M%S)

python3 -m backend.db.importers.import_assets_json
```

Restart and verify:

```bash
sudo systemctl restart nexus-api.service
sudo systemctl status nexus-api.service --no-pager
/tmp/nexus-cmdb-m1/scripts/verify_cmdb_postgres_milestone_1.sh
```

Expected API source: `nexus-postgresql-cmdb`. Expected count: `4`.

## GitHub

After verification:

```bash
git status
git add \
  backend/db/connection.py \
  backend/db/importers \
  backend/db/repositories \
  backend/services \
  backend/modules/cmdb.py \
  backend/db/migrations \
  scripts/setup_nexus_database.sh \
  docs/NEXUS_DATABASE_ARCHITECTURE.md \
  docs/NEXUS_DATABASE_PAGE_INTEGRATION.md

git commit -m "Add PostgreSQL CMDB foundation and asset repository"
git push origin feature/discovery-engine-v2
```

Do not commit `backend/data/private/` or runtime JSON/JSONL files.
