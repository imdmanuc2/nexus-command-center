# Package 010 — Automatic Sync and Stale Reconciliation

This package turns the manual Platform inventory import into a scheduled
PostgreSQL synchronization job.

Every minute it:

1. Reads the live Nexus mining and CMDB APIs.
2. Upserts pools, workers, workloads, and relationships.
3. Marks workers offline after five minutes without an observation.
4. Marks their workloads offline.
5. Marks their active worker relationships inactive.
6. Marks pools offline after five minutes without an observation.

## Install

```bash
chmod +x scripts/*.sh
./scripts/doctor.sh
./scripts/install.sh
./scripts/verify.sh
```

## Useful commands

Run immediately:

```bash
sudo systemctl start nexus-platform-sync.service
```

Follow logs:

```bash
sudo journalctl -u nexus-platform-sync.service -f
```

Check schedule:

```bash
systemctl list-timers nexus-platform-sync.timer
```

Dry-run stale reconciliation:

```bash
python3 -m backend.jobs.platform_sync_job \
  --stale-seconds 300 \
  --dry-run
```

## Rollback

```bash
./scripts/rollback.sh
```

## Commit

```bash
git add \
  backend/jobs/__init__.py \
  backend/jobs/platform_sync_job.py

git commit -m "Automate Platform inventory synchronization"
git push origin feature/discovery-engine-v2
```
