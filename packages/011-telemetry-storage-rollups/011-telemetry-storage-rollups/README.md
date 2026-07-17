# Package 011 — Telemetry Storage and Rollups

Adds PostgreSQL current metrics, raw history, 1-minute/hourly/daily rollups,
retention, a one-minute collector timer, and Platform Metrics APIs.

Install:

```bash
chmod +x scripts/*.sh scripts/patch_server.py
./scripts/doctor.sh
./scripts/install.sh
./scripts/verify.sh
```

APIs:

- `/api/platform/metrics`
- `/api/platform/metrics/current`
- `/api/platform/metrics/history`
- `/api/platform/metrics/rollups`
