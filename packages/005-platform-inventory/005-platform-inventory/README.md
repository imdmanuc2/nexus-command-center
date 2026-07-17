# Package 005 — Platform Inventory

Adds PostgreSQL repositories and APIs for:

- globally unique pool instances
- CPU/GPU/ASIC/FPGA workers
- mining and compute workloads
- persistent topology relationships

## Install

```bash
chmod +x scripts/*.sh
./scripts/install.sh

sudo systemctl restart nexus-api.service
sudo systemctl status nexus-api.service --no-pager

./scripts/verify.sh
```

## New APIs

- `GET /api/platform/inventory`
- `GET /api/platform/topology`

## Git commit

```bash
git add   backend/db/repositories/pool_repository.py   backend/db/repositories/worker_repository.py   backend/db/repositories/workload_repository.py   backend/db/repositories/relationship_repository.py   backend/services/platform_inventory_service.py   backend/modules/platform_inventory.py   scripts/sync_platform_inventory.py   backend/api/server.py

git commit -m "Add PostgreSQL workers pools workloads and topology"
git push origin feature/discovery-engine-v2
```
