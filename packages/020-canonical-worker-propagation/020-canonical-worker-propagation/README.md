# Package 020 — Canonical Worker Propagation

Completes worker identity reconciliation by using the `workerId` returned from
`upsert_worker()` for all downstream workload and relationship records.

## Install

```bash
chmod +x scripts/*.sh scripts/*.py
./scripts/doctor.sh
./scripts/install.sh
./scripts/verify.sh
```

## Expected result

- Platform inventory sync completes.
- Integrated Platform sync completes.
- No workload references a non-existent worker.
- `orphaned_workloads` returns `0`.

## Commit

```bash
git add scripts/sync_platform_inventory.py
git commit -m "Propagate canonical worker identity"
git push origin feature/discovery-engine-v2
```
